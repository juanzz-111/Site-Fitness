from flask import (
    Flask, render_template, request, redirect,
    url_for, session
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from functools import wraps
from pathlib import Path
from datetime import datetime
import os
import json
import uuid
import math


# ==========================================
# CONFIGURAÇÕES INICIAIS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    raise ValueError("SECRET_KEY não configurada no arquivo .env.")

app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024  # 3 MB
csrf = CSRFProtect(app)

DATABASE_PATH = BASE_DIR / "data" / "database.json"
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
DEFAULT_AVATAR = "images/default_avatar.png"
EXTENSOES_PERMITIDAS = {"png", "jpg", "jpeg", "webp"}


# ==========================================
# BANCO DE DADOS
# ==========================================

def carregar_usuarios():
    if not DATABASE_PATH.exists():
        return []

    with open(DATABASE_PATH, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    if not isinstance(dados, list):
        raise ValueError("O arquivo database.json deve conter uma lista.")

    # Compatibilidade com contas antigas que ainda não tinham foto_perfil.
    alterado = False
    for usuario in dados:
        if not usuario.get("foto_perfil"):
            usuario["foto_perfil"] = DEFAULT_AVATAR
            alterado = True

    if alterado:
        salvar_usuarios(dados)

    return dados


def salvar_usuarios(usuarios):
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(DATABASE_PATH, "w", encoding="utf-8") as arquivo:
        json.dump(
            usuarios,
            arquivo,
            ensure_ascii=False,
            indent=4
        )


# ==========================================
# FOTO DE PERFIL
# ==========================================

def arquivo_e_imagem_valida(arquivo, extensao):
    """Confere a assinatura real do arquivo, além da extensão."""
    inicio = arquivo.read(12)
    arquivo.seek(0)

    if extensao == "png":
        return inicio.startswith(b"\x89PNG\r\n\x1a\n")

    if extensao in {"jpg", "jpeg"}:
        return inicio.startswith(b"\xff\xd8\xff")

    if extensao == "webp":
        return (
            len(inicio) >= 12
            and inicio[0:4] == b"RIFF"
            and inicio[8:12] == b"WEBP"
        )

    return False


def salvar_foto_perfil(arquivo):
    """
    Salva a foto em static/uploads e devolve o caminho relativo
    usado por url_for('static', filename=...).
    """
    if arquivo is None or not arquivo.filename:
        return None, None

    nome_seguro = secure_filename(arquivo.filename)
    if "." not in nome_seguro:
        return None, "Arquivo de imagem inválido."

    extensao = nome_seguro.rsplit(".", 1)[1].lower()

    if extensao not in EXTENSOES_PERMITIDAS:
        return None, "Formato não permitido. Use PNG, JPG, JPEG ou WEBP."

    if not arquivo_e_imagem_valida(arquivo, extensao):
        return None, "O arquivo selecionado não é uma imagem válida."

    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    nome_final = f"{uuid.uuid4().hex}.{extensao}"
    caminho = UPLOAD_FOLDER / nome_final
    arquivo.save(caminho)

    return f"uploads/{nome_final}", None


def remover_foto_antiga(caminho_foto):
    """Remove somente arquivos antigos que estejam dentro de static/uploads."""
    if not caminho_foto or not caminho_foto.startswith("uploads/"):
        return

    caminho = (BASE_DIR / "static" / caminho_foto).resolve()
    pasta_uploads = UPLOAD_FOLDER.resolve()

    try:
        caminho.relative_to(pasta_uploads)
    except ValueError:
        return

    if caminho.is_file():
        caminho.unlink()


@app.errorhandler(413)
def arquivo_muito_grande(_erro):
    return "A imagem deve ter no máximo 3 MB.", 413


# ==========================================
# BUSCA DO USUÁRIO E PROTEÇÃO DE ROTAS
# ==========================================

def buscar_usuario_logado():
    user_id = session.get("user_id")
    if not user_id:
        return None

    return next(
        (
            usuario for usuario in carregar_usuarios()
            if usuario.get("id") == user_id
            and not usuario.get("excluido", False)
        ),
        None
    )


def login_required(func):
    @wraps(func)
    def verificar_login(*args, **kwargs):
        usuario = buscar_usuario_logado()

        if usuario is None:
            session.clear()
            return redirect(url_for("login"))

        session["email"] = usuario["email"]
        session["funcao"] = usuario["funcao"]
        return func(*args, **kwargs)

    return verificar_login


def admin_required(func):
    @wraps(func)
    def verificar_admin(*args, **kwargs):
        usuario = buscar_usuario_logado()

        if usuario is None:
            session.clear()
            return redirect(url_for("login"))

        session["email"] = usuario["email"]
        session["funcao"] = usuario["funcao"]

        if usuario.get("funcao") != "admin":
            return "Acesso negado: somente administradores podem acessar esta página.", 403

        return func(*args, **kwargs)

    return verificar_admin


# ==========================================
# INICIALIZAÇÃO DO ADMINISTRADOR
# ==========================================

def inicializar_administrador():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DATABASE_PATH.exists():
        salvar_usuarios([])

    usuarios = carregar_usuarios()

    admin_nome = os.getenv("ADMIN_NAME", "Administrador")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_senha = os.getenv("ADMIN_PASSWORD")

    if not admin_email or not admin_senha:
        raise ValueError(
            "Configure ADMIN_EMAIL e ADMIN_PASSWORD no arquivo .env."
        )

    admin_email = admin_email.strip().lower()

    if any(
        usuario.get("funcao") == "admin"
        and not usuario.get("excluido", False)
        for usuario in usuarios
    ):
        return

    usuario_existente = next(
        (
            usuario for usuario in usuarios
            if usuario.get("email", "").lower() == admin_email
        ),
        None
    )

    if usuario_existente is not None:
        if usuario_existente.get("funcao") != "admin":
            raise ValueError(
                "O e-mail do administrador já pertence a outro usuário."
            )

        usuario_existente["nome"] = admin_nome
        usuario_existente["senha_hash"] = generate_password_hash(
            admin_senha,
            method="pbkdf2:sha256"
        )
        usuario_existente["excluido"] = False
        usuario_existente.setdefault("foto_perfil", DEFAULT_AVATAR)
        salvar_usuarios(usuarios)
        print("Administrador existente reativado com sucesso!")
        return

    novo_admin = {
        "id": str(uuid.uuid4()),
        "nome": admin_nome,
        "email": admin_email,
        "senha_hash": generate_password_hash(
            admin_senha,
            method="pbkdf2:sha256"
        ),
        "foto_perfil": DEFAULT_AVATAR,
        "data_cadastro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "funcao": "admin",
        "excluido": False
    }

    usuarios.append(novo_admin)
    salvar_usuarios(usuarios)
    print("Administrador inicial criado com sucesso!")


# ==========================================
# PÁGINA INICIAL E SOBRE
# ==========================================

@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ==========================================
# CADASTRO
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        confirmar_senha = request.form.get("confirmar_senha", "")

        if not nome or not email or not senha or not confirmar_senha:
            return render_template(
                "register.html",
                erro="Preencha todos os campos obrigatórios.",
                nome=nome,
                email=email
            )

        if senha != confirmar_senha:
            return render_template(
                "register.html",
                erro="As senhas não são iguais.",
                nome=nome,
                email=email
            )

        usuarios = carregar_usuarios()

        if any(
            usuario.get("email", "").lower() == email
            for usuario in usuarios
        ):
            return render_template(
                "register.html",
                erro="Este e-mail já está cadastrado.",
                nome=nome,
                email=email
            )

        foto_perfil, erro_foto = salvar_foto_perfil(
            request.files.get("foto_perfil")
        )

        if erro_foto:
            return render_template(
                "register.html",
                erro=erro_foto,
                nome=nome,
                email=email
            )

        novo_usuario = {
            "id": str(uuid.uuid4()),
            "nome": nome,
            "email": email,
            "senha_hash": generate_password_hash(
                senha,
                method="pbkdf2:sha256"
            ),
            "foto_perfil": foto_perfil or DEFAULT_AVATAR,
            "data_cadastro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "funcao": "comum",
            "excluido": False
        }

        usuarios.append(novo_usuario)
        salvar_usuarios(usuarios)

        return render_template(
            "register.html",
            sucesso="Cadastro realizado com sucesso!"
        )

    return render_template("register.html")


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        usuarios = carregar_usuarios()

        usuario = next(
            (
                u for u in usuarios
                if u.get("email", "").lower() == email
            ),
            None
        )

        if usuario is None or usuario.get("excluido", False):
            return render_template(
                "login.html",
                erro="E-mail ou senha incorretos.",
                email=email
            )

        if not check_password_hash(usuario["senha_hash"], senha):
            return render_template(
                "login.html",
                erro="E-mail ou senha incorretos.",
                email=email
            )

        session.clear()
        session["user_id"] = usuario["id"]
        session["email"] = usuario["email"]
        session["funcao"] = usuario["funcao"]

        return redirect(url_for("inicio"))

    return render_template("login.html")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==========================================
# PERFIL
# ==========================================

@app.route("/profile")
@login_required
def profile():
    usuario = buscar_usuario_logado()

    if usuario is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        nome=usuario["nome"],
        email=usuario["email"],
        foto_perfil=usuario.get("foto_perfil", DEFAULT_AVATAR),
        idade=usuario.get("idade"),
        peso=usuario.get("peso"),
        altura=usuario.get("altura"),
        sexo=usuario.get("sexo")
    )


# ==========================================
# EDIÇÃO DO PRÓPRIO PERFIL
# ==========================================

@app.route("/editar_perfil", methods=["GET", "POST"])
@login_required
def editar_perfil():
    usuarios = carregar_usuarios()

    usuario = next(
        (
            u for u in usuarios
            if u.get("id") == session.get("user_id")
            and not u.get("excluido", False)
        ),
        None
    )

    if usuario is None:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        if not nome or not email:
            return render_template(
                "editar_perfil.html",
                nome=nome,
                email=email,
                foto_perfil=usuario.get("foto_perfil", DEFAULT_AVATAR),
                erro="Preencha os campos obrigatórios."
            )

        email_em_uso = any(
            u.get("email", "").lower() == email
            and u.get("id") != usuario["id"]
            for u in usuarios
        )

        if email_em_uso:
            return render_template(
                "editar_perfil.html",
                nome=nome,
                email=email,
                foto_perfil=usuario.get("foto_perfil", DEFAULT_AVATAR),
                erro="Este e-mail já está cadastrado."
            )

        novo_caminho_foto, erro_foto = salvar_foto_perfil(
            request.files.get("foto_perfil")
        )

        if erro_foto:
            return render_template(
                "editar_perfil.html",
                nome=nome,
                email=email,
                foto_perfil=usuario.get("foto_perfil", DEFAULT_AVATAR),
                erro=erro_foto
            )

        foto_antiga = usuario.get("foto_perfil", DEFAULT_AVATAR)

        usuario["nome"] = nome
        usuario["email"] = email

        if senha:
            usuario["senha_hash"] = generate_password_hash(
                senha,
                method="pbkdf2:sha256"
            )

        if novo_caminho_foto:
            usuario["foto_perfil"] = novo_caminho_foto

        salvar_usuarios(usuarios)

        if novo_caminho_foto:
            remover_foto_antiga(foto_antiga)

        session["email"] = email
        return redirect(url_for("profile"))

    return render_template(
        "editar_perfil.html",
        nome=usuario["nome"],
        email=usuario["email"],
        foto_perfil=usuario.get("foto_perfil", DEFAULT_AVATAR)
    )


# ==========================================
# PAINEL ADMINISTRATIVO
# ==========================================

@app.route("/admin")
@admin_required
def admin_dashboard():
    usuarios = carregar_usuarios()

    usuarios_visiveis = []
    for usuario in usuarios:
        usuarios_visiveis.append({
            "id": usuario["id"],
            "nome": usuario["nome"],
            "email": usuario["email"],
            "funcao": usuario["funcao"],
            "data_cadastro": usuario["data_cadastro"],
            "foto_perfil": usuario.get("foto_perfil", DEFAULT_AVATAR),
            "excluido": usuario.get("excluido", False)
        })

    total_usuarios = len(usuarios)
    total_admins = sum(
        1 for u in usuarios if u.get("funcao") == "admin"
    )
    total_comuns = sum(
        1 for u in usuarios if u.get("funcao") == "comum"
    )

    return render_template(
        "admin_dashboard.html",
        usuarios=usuarios_visiveis,
        total_usuarios=total_usuarios,
        total_admins=total_admins,
        total_comuns=total_comuns
    )


# ==========================================
# EDIÇÃO DE USUÁRIO PELO ADMINISTRADOR
# ==========================================

@app.route("/admin/editar/<usuario_id>", methods=["GET", "POST"])
@admin_required
def editar_usuario(usuario_id):
    usuarios = carregar_usuarios()

    usuario = next(
        (u for u in usuarios if u.get("id") == usuario_id),
        None
    )

    if usuario is None:
        return "Usuário não encontrado.", 404

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        funcao = request.form.get("funcao", "")

        if not nome or not email or funcao not in ["comum", "admin"]:
            return render_template(
                "editar_perfil.html",
                usuario=usuario,
                modo_admin=True,
                erro="Preencha os campos corretamente."
            )

        email_em_uso = any(
            u.get("email", "").lower() == email
            and u.get("id") != usuario_id
            for u in usuarios
        )

        if email_em_uso:
            return render_template(
                "editar_perfil.html",
                usuario=usuario,
                modo_admin=True,
                erro="Este e-mail já está cadastrado."
            )

        if (
            usuario.get("funcao") == "admin"
            and funcao == "comum"
            and not usuario.get("excluido", False)
        ):
            outros_admins_ativos = sum(
                1 for u in usuarios
                if u.get("funcao") == "admin"
                and not u.get("excluido", False)
                and u.get("id") != usuario_id
            )

            if outros_admins_ativos == 0:
                return render_template(
                    "editar_perfil.html",
                    usuario=usuario,
                    modo_admin=True,
                    erro="Não é possível rebaixar o último administrador ativo."
                ), 403

        novo_caminho_foto, erro_foto = salvar_foto_perfil(
            request.files.get("foto_perfil")
        )

        if erro_foto:
            return render_template(
                "editar_perfil.html",
                usuario=usuario,
                modo_admin=True,
                erro=erro_foto
            )

        foto_antiga = usuario.get("foto_perfil", DEFAULT_AVATAR)

        usuario["nome"] = nome
        usuario["email"] = email
        usuario["funcao"] = funcao

        if novo_caminho_foto:
            usuario["foto_perfil"] = novo_caminho_foto

        salvar_usuarios(usuarios)

        if novo_caminho_foto:
            remover_foto_antiga(foto_antiga)

        if usuario_id == session.get("user_id"):
            session["email"] = email
            session["funcao"] = funcao

            if funcao != "admin":
                return redirect(url_for("profile"))

        return redirect(url_for("admin_dashboard"))

    return render_template(
        "editar_perfil.html",
        usuario=usuario,
        modo_admin=True
    )


# ==========================================
# DESATIVAR / REATIVAR USUÁRIO
# ==========================================

@app.route("/admin/alternar-status/<usuario_id>", methods=["POST"])
@admin_required
def alternar_status_usuario(usuario_id):
    usuarios = carregar_usuarios()

    usuario = next(
        (u for u in usuarios if u.get("id") == usuario_id),
        None
    )

    if usuario is None:
        return "Usuário não encontrado.", 404

    if (
        usuario_id == session.get("user_id")
        and not usuario.get("excluido", False)
    ):
        return "Você não pode desativar sua própria conta.", 403

    if (
        usuario.get("funcao") == "admin"
        and not usuario.get("excluido", False)
    ):
        outros_admins_ativos = sum(
            1 for u in usuarios
            if u.get("funcao") == "admin"
            and not u.get("excluido", False)
            and u.get("id") != usuario_id
        )

        if outros_admins_ativos == 0:
            return "Não é possível desativar o último administrador ativo.", 403

    usuario["excluido"] = not usuario.get("excluido", False)
    salvar_usuarios(usuarios)

    return redirect(url_for("admin_dashboard"))


# ==========================================
# RECEBER FORMULÁRIO DO IMC
# ==========================================

@app.route("/calcular-imc", methods=["POST"])
def calcular_imc():
    try:
        peso = float(request.form.get("peso", ""))
        altura = float(request.form.get("altura", ""))
        idade = int(request.form.get("idade", ""))
        sexo = request.form.get("sexo", "")
    except (TypeError, ValueError):
        return "Informe valores numéricos válidos para calcular o IMC.", 400

    if not all(math.isfinite(valor) for valor in [peso, altura]):
        return "Os valores informados são inválidos.", 400

    if peso <= 0 or peso > 500:
        return "Informe um peso válido.", 400

    if altura <= 0 or altura > 3:
        return "Informe uma altura válida.", 400

    if idade < 1 or idade > 120:
        return "Informe uma idade válida.", 400

    if sexo not in ["masculino", "feminino"]:
        return "Selecione uma opção válida para sexo.", 400

    # Se houver um usuário autenticado, salva os dados enviados
    # para que possam ser exibidos posteriormente no perfil.
    usuario_logado = buscar_usuario_logado()

    if usuario_logado is not None:
        usuarios = carregar_usuarios()

        for usuario in usuarios:
            if usuario.get("id") == usuario_logado.get("id"):
                usuario["peso"] = peso
                usuario["altura"] = altura
                usuario["idade"] = idade
                usuario["sexo"] = sexo
                break

        salvar_usuarios(usuarios)

    return redirect(
        url_for(
            "imc",
            peso=peso,
            altura=altura,
            sexo=sexo,
            idade=idade
        )
    )


# ==========================================
# CALCULADORA / RESULTADO DO IMC
# ==========================================

@app.route("/imc")
@app.route("/imc/<float:peso>/<float:altura>")
def imc(peso=None, altura=None):
    if peso is None:
        peso = request.args.get("peso", type=float)
        altura = request.args.get("altura", type=float)

    if peso is None or altura is None:
        return render_template("imc.html")

    sexo = request.args.get("sexo", "")
    idade = request.args.get("idade", default=0, type=int)

    if (
        not math.isfinite(peso)
        or not math.isfinite(altura)
        or peso <= 0
        or altura <= 0
        or idade < 0
        or idade > 120
    ):
        return "Dados inválidos para o cálculo do IMC.", 400

    if sexo not in ["", "masculino", "feminino"]:
        return "Sexo informado inválido.", 400

    valor_imc = round(peso / (altura ** 2), 2)

    if valor_imc < 18.5:
        classificacao = "Magreza"
    elif valor_imc < 25:
        classificacao = "Normal"
    elif valor_imc < 30:
        classificacao = "Sobrepeso"
    else:
        classificacao = "Obesidade"

    peso_ideal = round(22 * (altura ** 2), 2)

    sexo_formula = 1 if sexo == "masculino" else 0
    percentual_gordura = round(
        1.20 * valor_imc + 0.23 * idade - 10.8 * sexo_formula - 5.4,
        1
    )

    if sexo == "masculino":
        if percentual_gordura < 2:
            classificacao_gordura = "Essencial"
        elif percentual_gordura < 14:
            classificacao_gordura = "Atlético"
        elif percentual_gordura < 18:
            classificacao_gordura = "Fitness"
        elif percentual_gordura < 25:
            classificacao_gordura = "Aceitável"
        else:
            classificacao_gordura = "Obesidade"
    else:
        if percentual_gordura < 10:
            classificacao_gordura = "Essencial"
        elif percentual_gordura < 21:
            classificacao_gordura = "Atlético"
        elif percentual_gordura < 25:
            classificacao_gordura = "Fitness"
        elif percentual_gordura < 32:
            classificacao_gordura = "Aceitável"
        else:
            classificacao_gordura = "Obesidade"

    if classificacao_gordura == "Essencial":
        recomendacoes = [
            "Procure orientação de um profissional de saúde para avaliar o resultado.",
            "Mantenha hábitos de cuidado e bem-estar."
        ]
    elif classificacao_gordura == "Atlético":
        recomendacoes = [
            "Mantenha hábitos alimentares equilibrados.",
            "Cuide do sono, da alimentação e da atividade física."
        ]
    elif classificacao_gordura == "Fitness":
        recomendacoes = [
            "Mantenha uma alimentação equilibrada.",
            "Continue cuidando da sua saúde de forma adequada."
        ]
    elif classificacao_gordura == "Aceitável":
        recomendacoes = [
            "Priorize uma alimentação equilibrada e variada.",
            "Mantenha hábitos saudáveis conforme sua condição."
        ]
    else:
        recomendacoes = [
            "Considere conversar com um profissional de saúde sobre o resultado.",
            "Procure manter hábitos de alimentação, sono e atividade física saudáveis."
        ]

    if valor_imc < 18.5:
        posicao = (valor_imc / 18.5) * 25
    elif valor_imc < 25:
        posicao = 25 + ((valor_imc - 18.5) / 6.5) * 25
    elif valor_imc < 30:
        posicao = 50 + ((valor_imc - 25) / 5) * 25
    else:
        posicao = min(100, 75 + ((valor_imc - 30) / 10) * 25)

    return render_template(
        "imc.html",
        peso=peso,
        altura=altura,
        sexo=sexo,
        idade=idade,
        imc=valor_imc,
        classificacao=classificacao,
        peso_ideal=peso_ideal,
        percentual_gordura=percentual_gordura,
        classificacao_gordura=classificacao_gordura,
        recomendacoes=recomendacoes,
        posicao=posicao
    )


# ==========================================
# RECEBER FORMULÁRIO MATEMÁTICO
# ==========================================

@app.route("/calcular-math", methods=["POST"])
def calcular_math():
    operacao = request.form.get("operacao", "")

    try:
        numero1 = float(request.form.get("numero1", ""))
        numero2 = float(request.form.get("numero2", ""))
    except (TypeError, ValueError):
        return "Informe dois números válidos.", 400

    if not math.isfinite(numero1) or not math.isfinite(numero2):
        return "Os números informados são inválidos.", 400

    if operacao not in ["soma", "subtracao", "multiplicacao", "divisao"]:
        return "Operação inválida.", 400

    return redirect(
        url_for(
            "math_resultado",
            op=operacao,
            a=numero1,
            b=numero2
        )
    )


# ==========================================
# RESULTADO MATEMÁTICO
# ==========================================

@app.route("/math/<op>/<float:a>/<float:b>")
def math_resultado(op, a, b):
    if not math.isfinite(a) or not math.isfinite(b):
        return "Números inválidos.", 400

    if op == "soma":
        resultado = a + b
        nome_operacao = "Soma"
        simbolo = "+"
    elif op == "subtracao":
        resultado = a - b
        nome_operacao = "Subtração"
        simbolo = "-"
    elif op == "multiplicacao":
        resultado = a * b
        nome_operacao = "Multiplicação"
        simbolo = "×"
    elif op == "divisao":
        nome_operacao = "Divisão"
        simbolo = "÷"
        if b == 0:
            resultado = "Não é possível dividir por zero."
        else:
            resultado = round(a / b, 2)
    else:
        return "Operação inválida.", 400

    return render_template(
        "math.html",
        operacao=nome_operacao,
        simbolo=simbolo,
        a=a,
        b=b,
        resultado=resultado
    )


# ==========================================
# EXECUTAR SERVIDOR
# ==========================================

if __name__ == "__main__":
    inicializar_administrador()

    app.run(
        host="0.0.0.0",
        port=5002,
        debug=False
    )