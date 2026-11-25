from flask import Flask, render_template, request, redirect, url_for, session

from werkzeug.security import generate_password_hash, check_password_hash

from dotenv import load_dotenv

from flask_wtf.csrf import CSRFProtect

from functools import wraps

import os
import json
import uuid
import math

from pathlib import Path
from datetime import datetime


# ==========================================
# CONFIGURAÇÕES INICIAIS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / '.env')

app = Flask(__name__)

app.secret_key = os.getenv('SECRET_KEY')

if not app.secret_key:
    raise ValueError('SECRET_KEY não configurada no arquivo .env.')

# Proteção CSRF em todos os formulários POST
csrf = CSRFProtect(app)

# Caminho do banco de dados
DATABASE_PATH = BASE_DIR / 'data' / 'database.json'


# ==========================================
# FUNÇÕES DO BANCO DE DADOS
# ==========================================

def carregar_usuarios():

    if not DATABASE_PATH.exists():
        return []

    with open(DATABASE_PATH, 'r', encoding='utf-8') as arquivo:
        return json.load(arquivo)


def salvar_usuarios(usuarios):

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(DATABASE_PATH, 'w', encoding='utf-8') as arquivo:

        json.dump(
            usuarios,
            arquivo,
            ensure_ascii=False,
            indent=4
        )


# ==========================================
# PROTEÇÃO DE ACESSO
# ==========================================

def buscar_usuario_logado():

    if 'user_id' not in session:
        return None

    usuarios = carregar_usuarios()

    usuario = next(
        (
            u for u in usuarios
            if u.get('id') == session.get('user_id')
            and not u.get('excluido', False)
        ),
        None
    )

    return usuario


def login_required(func):

    @wraps(func)
    def verificar_login(*args, **kwargs):

        usuario = buscar_usuario_logado()

        if usuario is None:
            session.clear()
            return redirect(url_for('login'))

        session['email'] = usuario['email']
        session['funcao'] = usuario['funcao']

        return func(*args, **kwargs)

    return verificar_login


def admin_required(func):

    @wraps(func)
    def verificar_admin(*args, **kwargs):

        usuario = buscar_usuario_logado()

        if usuario is None:
            session.clear()
            return redirect(url_for('login'))

        session['email'] = usuario['email']
        session['funcao'] = usuario['funcao']

        if usuario.get('funcao') != 'admin':
            return 'Acesso negado: somente administradores podem acessar esta página.', 403

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

    admin_nome = os.getenv('ADMIN_NAME', 'Administrador')
    admin_email = os.getenv('ADMIN_EMAIL')
    admin_senha = os.getenv('ADMIN_PASSWORD')

    if not admin_email or not admin_senha:
        raise ValueError(
            'Configure ADMIN_EMAIL e ADMIN_PASSWORD no arquivo .env.'
        )

    admin_email = admin_email.strip().lower()

    # Verifica se já existe um administrador ativo
    if any(
        usuario.get('funcao') == 'admin'
        and not usuario.get('excluido', False)
        for usuario in usuarios
    ):
        return

    # Verifica se o e-mail já pertence a algum usuário
    usuario_existente = next(
        (
            usuario for usuario in usuarios
            if usuario.get('email', '').lower() == admin_email
        ),
        None
    )

    # Se já existe uma conta administrativa desativada,
    # reativa essa conta usando as credenciais do .env.
    if usuario_existente is not None:

        if usuario_existente.get('funcao') != 'admin':
            raise ValueError(
                'O e-mail do administrador já pertence a outro usuário.'
            )

        usuario_existente['nome'] = admin_nome
        usuario_existente['senha_hash'] = generate_password_hash(
            admin_senha,
            method='pbkdf2:sha256'
        )
        usuario_existente['excluido'] = False

        salvar_usuarios(usuarios)

        print('Administrador existente reativado com sucesso!')

        return

    # Criar novo administrador
    novo_admin = {

        'id': str(uuid.uuid4()),

        'nome': admin_nome,

        'email': admin_email,

        'senha_hash': generate_password_hash(
            admin_senha,
            method='pbkdf2:sha256'
        ),

        'foto_perfil': 'default_avatar.png',

        'data_cadastro': datetime.now().isoformat(timespec='seconds'),

        'funcao': 'admin',

        'excluido': False
    }

    usuarios.append(novo_admin)

    salvar_usuarios(usuarios)

    print('Administrador inicial criado com sucesso!')


# ==========================================
# PÁGINA INICIAL
# ==========================================

@app.route('/')
def inicio():

    return render_template('index.html')


# ==========================================
# PÁGINA SOBRE
# ==========================================

@app.route('/about')
def about():

    return render_template('about.html')


# ==========================================
# CADASTRO DE USUÁRIOS
# ==========================================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        confirmar_senha = request.form.get('confirmar_senha', '')

        # Verificar se todos os campos foram preenchidos
        if not nome or not email or not senha or not confirmar_senha:

            return render_template(
                'register.html',
                erro='Preencha todos os campos.',
                nome=nome,
                email=email
            )

        # Verificar se as senhas são iguais
        if senha != confirmar_senha:

            return render_template(
                'register.html',
                erro='As senhas não são iguais.',
                nome=nome,
                email=email
            )

        usuarios = carregar_usuarios()

        # Verificar se o e-mail já está cadastrado
        if any(
            usuario.get('email', '').lower() == email
            for usuario in usuarios
        ):

            return render_template(
                'register.html',
                erro='Este e-mail já está cadastrado.',
                nome=nome,
                email=email
            )

        # Criar novo usuário
        novo_usuario = {

            'id': str(uuid.uuid4()),

            'nome': nome,

            'email': email,

            'senha_hash': generate_password_hash(
                senha,
                method='pbkdf2:sha256'
            ),

            'foto_perfil': 'default_avatar.png',

            'data_cadastro': datetime.now().isoformat(timespec='seconds'),

            # Cadastro público sempre cria usuário comum
            'funcao': 'comum',

            'excluido': False
        }

        # Adicionar usuário à lista
        usuarios.append(novo_usuario)

        # Salvar no JSON
        salvar_usuarios(usuarios)

        return render_template(
            'register.html',
            sucesso='Cadastro realizado com sucesso!'
        )

    return render_template('register.html')


# ==========================================
# LOGIN
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')

        usuarios = carregar_usuarios()

        # Procurar usuário pelo e-mail
        usuario = next(
            (
                u for u in usuarios
                if u.get('email', '').lower() == email
            ),
            None
        )

        # Verificar se o usuário existe e está ativo
        if usuario is None or usuario.get('excluido', False):

            return render_template(
                'login.html',
                erro='E-mail ou senha incorretos.',
                email=email
            )

        # Verificar a senha
        if not check_password_hash(usuario['senha_hash'], senha):

            return render_template(
                'login.html',
                erro='E-mail ou senha incorretos.',
                email=email
            )

        # Criar sessão do usuário
        session.clear()

        session['user_id'] = usuario['id']
        session['email'] = usuario['email']
        session['funcao'] = usuario['funcao']

        # Redirecionar para a página inicial
        return redirect(url_for('inicio'))

    return render_template('login.html')


# ==========================================
# LOGOUT
# ==========================================

@app.route('/logout', methods=['POST'])
@login_required
def logout():

    session.clear()

    return redirect(url_for('login'))


# ==========================================
# PERFIL DO USUÁRIO
# ==========================================

@app.route('/profile')
@login_required
def profile():

    usuario = buscar_usuario_logado()

    if usuario is None:
        session.clear()
        return redirect(url_for('login'))

    return render_template(
        'profile.html',
        nome=usuario['nome'],
        email=usuario['email'],
        foto_perfil=usuario.get('foto_perfil', 'default_avatar.png'),
        idade=None,
        peso=None,
        altura=None,
        sexo=None
    )


# ==========================================
# EDITAR PERFIL DO USUÁRIO
# ==========================================

@app.route('/editar_perfil', methods=['GET', 'POST'])
@login_required
def editar_perfil():

    usuarios = carregar_usuarios()

    usuario = next(
        (
            u for u in usuarios
            if u.get('id') == session.get('user_id')
            and not u.get('excluido', False)
        ),
        None
    )

    if usuario is None:
        session.clear()
        return redirect(url_for('login'))

    if request.method == 'POST':

        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')

        if not nome or not email:

            return render_template(
                'editar_perfil.html',
                nome=nome,
                email=email,
                erro='Preencha todos os campos obrigatórios.'
            )

        email_em_uso = any(
            u.get('email', '').lower() == email
            and u.get('id') != usuario['id']
            for u in usuarios
        )

        if email_em_uso:

            return render_template(
                'editar_perfil.html',
                nome=nome,
                email=email,
                erro='Este e-mail já está cadastrado.'
            )

        usuario['nome'] = nome
        usuario['email'] = email

        if senha:

            usuario['senha_hash'] = generate_password_hash(
                senha,
                method='pbkdf2:sha256'
            )

        salvar_usuarios(usuarios)

        session['email'] = email

        return redirect(url_for('profile'))

    return render_template(
        'editar_perfil.html',
        nome=usuario['nome'],
        email=usuario['email']
    )


# ==========================================
# PAINEL ADMINISTRATIVO
# ==========================================

@app.route('/admin')
@admin_required
def admin_dashboard():

    usuarios = carregar_usuarios()

    # Remover informações privadas antes de enviar ao HTML
    usuarios_visiveis = []

    for usuario in usuarios:

        usuarios_visiveis.append({

            'id': usuario['id'],

            'nome': usuario['nome'],

            'email': usuario['email'],

            'funcao': usuario['funcao'],

            'data_cadastro': usuario['data_cadastro'],

            'excluido': usuario.get('excluido', False)

        })

    total_usuarios = len(usuarios)

    total_admins = sum(
        1 for u in usuarios
        if u.get('funcao') == 'admin'
    )

    total_comuns = sum(
        1 for u in usuarios
        if u.get('funcao') == 'comum'
    )

    return render_template(
        'admin_dashboard.html',
        usuarios=usuarios_visiveis,
        total_usuarios=total_usuarios,
        total_admins=total_admins,
        total_comuns=total_comuns
    )


# ==========================================
# EDITAR USUÁRIO PELO ADMINISTRADOR
# ==========================================

@app.route('/admin/editar/<usuario_id>', methods=['GET', 'POST'])
@admin_required
def editar_usuario(usuario_id):

    usuarios = carregar_usuarios()

    usuario = next(
        (u for u in usuarios if u.get('id') == usuario_id),
        None
    )

    if usuario is None:
        return 'Usuário não encontrado.', 404

    if request.method == 'POST':

        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        funcao = request.form.get('funcao', '')

        if not nome or not email or funcao not in ['comum', 'admin']:

            return render_template(
                'editar_perfil.html',
                usuario=usuario,
                modo_admin=True,
                erro='Preencha os campos corretamente.'
            )

        email_em_uso = any(
            u.get('email', '').lower() == email
            and u.get('id') != usuario_id
            for u in usuarios
        )

        if email_em_uso:

            return render_template(
                'editar_perfil.html',
                usuario=usuario,
                modo_admin=True,
                erro='Este e-mail já está cadastrado.'
            )

        # Impedir que o último administrador ativo seja rebaixado
        if (
            usuario.get('funcao') == 'admin'
            and funcao == 'comum'
            and not usuario.get('excluido', False)
        ):

            outros_admins_ativos = sum(
                1 for u in usuarios
                if u.get('funcao') == 'admin'
                and not u.get('excluido', False)
                and u.get('id') != usuario_id
            )

            if outros_admins_ativos == 0:

                return render_template(
                    'editar_perfil.html',
                    usuario=usuario,
                    modo_admin=True,
                    erro='Não é possível rebaixar o último administrador ativo.'
                ), 403

        usuario['nome'] = nome
        usuario['email'] = email
        usuario['funcao'] = funcao

        salvar_usuarios(usuarios)

        # Atualizar os dados da sessão se o administrador
        # estiver editando a própria conta.
        if usuario_id == session.get('user_id'):

            session['email'] = email
            session['funcao'] = funcao

            if funcao != 'admin':
                return redirect(url_for('profile'))

        return redirect(url_for('admin_dashboard'))

    return render_template(
        'editar_perfil.html',
        usuario=usuario,
        modo_admin=True
    )


# ==========================================
# DESATIVAR / REATIVAR USUÁRIO
# ==========================================

@app.route('/admin/alternar-status/<usuario_id>', methods=['POST'])
@admin_required
def alternar_status_usuario(usuario_id):

    usuarios = carregar_usuarios()

    usuario = next(
        (u for u in usuarios if u.get('id') == usuario_id),
        None
    )

    if usuario is None:
        return 'Usuário não encontrado.', 404

    # Impede o administrador de desativar a própria conta.
    if (
        usuario_id == session.get('user_id')
        and not usuario.get('excluido', False)
    ):

        return 'Você não pode desativar sua própria conta.', 403

    # Impede a desativação do último administrador ativo.
    if (
        usuario.get('funcao') == 'admin'
        and not usuario.get('excluido', False)
    ):

        outros_admins_ativos = sum(
            1 for u in usuarios
            if u.get('funcao') == 'admin'
            and not u.get('excluido', False)
            and u.get('id') != usuario_id
        )

        if outros_admins_ativos == 0:

            return 'Não é possível desativar o último administrador ativo.', 403

    # Inverte o status da conta.
    usuario['excluido'] = not usuario.get('excluido', False)

    salvar_usuarios(usuarios)

    return redirect(url_for('admin_dashboard'))


# ==========================================
# RECEBER FORMULÁRIO DO IMC
# ==========================================

@app.route('/calcular-imc', methods=['POST'])
def calcular_imc():

    try:

        peso = float(request.form.get('peso', ''))
        altura = float(request.form.get('altura', ''))
        idade = int(request.form.get('idade', ''))
        sexo = request.form.get('sexo', '')

    except (TypeError, ValueError):

        return 'Informe valores numéricos válidos para calcular o IMC.', 400

    # Verificar valores numéricos
    if not all(math.isfinite(valor) for valor in [peso, altura]):

        return 'Os valores informados são inválidos.', 400

    # Verificar limites dos dados
    if peso <= 0 or peso > 500:
        return 'Informe um peso válido.', 400

    if altura <= 0 or altura > 3:
        return 'Informe uma altura válida.', 400

    if idade < 1 or idade > 120:
        return 'Informe uma idade válida.', 400

    if sexo not in ['masculino', 'feminino']:
        return 'Selecione uma opção válida para sexo.', 400

    return redirect(
        url_for(
            'imc',
            peso=peso,
            altura=altura,
            sexo=sexo,
            idade=idade
        )
    )


# ==========================================
# CALCULADORA / RESULTADO DO IMC
# ==========================================

@app.route('/imc')
@app.route('/imc/<float:peso>/<float:altura>')
def imc(peso=None, altura=None):

    # Entrou diretamente em /imc
    if peso is None or altura is None:
        return render_template('imc.html')

    sexo = request.args.get('sexo', '')
    idade = request.args.get('idade', type=int)

    # Compatibilidade com acesso direto à rota antiga
    if idade is None:
        idade = 0

    # Validar os valores recebidos pela URL
    if (
        not math.isfinite(peso)
        or not math.isfinite(altura)
        or peso <= 0
        or altura <= 0
        or idade < 0
        or idade > 120
    ):

        return 'Dados inválidos para o cálculo do IMC.', 400

    if sexo not in ['', 'masculino', 'feminino']:
        return 'Sexo informado inválido.', 400

    # ======================================
    # CÁLCULO DO IMC
    # ======================================

    valor_imc = peso / (altura ** 2)

    valor_imc = round(valor_imc, 2)

    # ======================================
    # CLASSIFICAÇÃO DO IMC
    # ======================================

    if valor_imc < 18.5:
        classificacao = 'Magreza'

    elif valor_imc < 25:
        classificacao = 'Normal'

    elif valor_imc < 30:
        classificacao = 'Sobrepeso'

    else:
        classificacao = 'Obesidade'

    # ======================================
    # PESO IDEAL
    # ======================================

    peso_ideal = 22 * (altura ** 2)

    peso_ideal = round(peso_ideal, 2)

    # ======================================
    # PERCENTUAL DE GORDURA
    # FÓRMULA DE DEURENBERG
    # ======================================

    if sexo == 'masculino':
        sexo_formula = 1
    else:
        sexo_formula = 0

    percentual_gordura = (
        1.20 * valor_imc
        + 0.23 * idade
        - 10.8 * sexo_formula
        - 5.4
    )

    percentual_gordura = round(percentual_gordura, 1)

    # ======================================
    # CLASSIFICAÇÃO DA GORDURA
    # ======================================

    if sexo == 'masculino':

        if percentual_gordura < 2:
            classificacao_gordura = 'Essencial'

        elif percentual_gordura < 14:
            classificacao_gordura = 'Atlético'

        elif percentual_gordura < 18:
            classificacao_gordura = 'Fitness'

        elif percentual_gordura < 25:
            classificacao_gordura = 'Aceitável'

        else:
            classificacao_gordura = 'Obesidade'

    else:

        if percentual_gordura < 10:
            classificacao_gordura = 'Essencial'

        elif percentual_gordura < 21:
            classificacao_gordura = 'Atlético'

        elif percentual_gordura < 25:
            classificacao_gordura = 'Fitness'

        elif percentual_gordura < 32:
            classificacao_gordura = 'Aceitável'

        else:
            classificacao_gordura = 'Obesidade'

    # ======================================
    # RECOMENDAÇÕES
    # ======================================

    if classificacao_gordura == 'Essencial':

        recomendacoes = [
            'Procure orientação de um profissional de saúde para avaliar o resultado.',
            'Mantenha uma alimentação equilibrada e hábitos saudáveis.'
        ]

    elif classificacao_gordura == 'Atlético':

        recomendacoes = [
            'Mantenha hábitos alimentares equilibrados.',
            'Continue praticando atividades físicas de forma adequada e segura.'
        ]

    elif classificacao_gordura == 'Fitness':

        recomendacoes = [
            'Mantenha uma alimentação equilibrada.',
            'Continue com uma rotina regular de atividades físicas.'
        ]

    elif classificacao_gordura == 'Aceitável':

        recomendacoes = [
            'Priorize uma alimentação equilibrada e variada.',
            'Mantenha atividades físicas regulares conforme sua condição.'
        ]

    else:

        recomendacoes = [
            'Considere conversar com um profissional de saúde sobre o resultado.',
            'Procure manter hábitos de alimentação, sono e atividade física saudáveis.'
        ]

    # ======================================
    # POSIÇÃO DO MARCADOR DO IMC
    # ======================================

    if valor_imc < 18.5:

        posicao = (valor_imc / 18.5) * 25

    elif valor_imc < 25:

        posicao = 25 + ((valor_imc - 18.5) / 6.5) * 25

    elif valor_imc < 30:

        posicao = 50 + ((valor_imc - 25) / 5) * 25

    else:

        posicao = 75 + ((valor_imc - 30) / 10) * 25

        if posicao > 100:
            posicao = 100

    return render_template(
        'imc.html',
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

@app.route('/calcular-math', methods=['POST'])
def calcular_math():

    operacao = request.form.get('operacao', '')

    try:

        numero1 = float(request.form.get('numero1', ''))
        numero2 = float(request.form.get('numero2', ''))

    except (TypeError, ValueError):

        return 'Informe dois números válidos.', 400

    # Verificar valores numéricos
    if not math.isfinite(numero1) or not math.isfinite(numero2):

        return 'Os números informados são inválidos.', 400

    # Verificar operação
    if operacao not in [
        'soma',
        'subtracao',
        'multiplicacao',
        'divisao'
    ]:

        return 'Operação inválida.', 400

    return redirect(
        url_for(
            'math',
            op=operacao,
            a=numero1,
            b=numero2
        )
    )


# ==========================================
# RESULTADO MATEMÁTICO
# ==========================================

@app.route('/math/<op>/<float:a>/<float:b>')
def math_resultado(op, a, b):

    if not math.isfinite(a) or not math.isfinite(b):
        return 'Números inválidos.', 400

    if op == 'soma':

        resultado = a + b
        nome_operacao = 'Soma'
        simbolo = '+'

    elif op == 'subtracao':

        resultado = a - b
        nome_operacao = 'Subtração'
        simbolo = '-'

    elif op == 'multiplicacao':

        resultado = a * b
        nome_operacao = 'Multiplicação'
        simbolo = '×'

    elif op == 'divisao':

        nome_operacao = 'Divisão'
        simbolo = '÷'

        if b == 0:
            resultado = 'Não é possível dividir por zero.'
        else:
            resultado = round(a / b, 2)

    else:

        return 'Operação inválida.', 400

    return render_template(
        'math.html',
        operacao=nome_operacao,
        simbolo=simbolo,
        a=a,
        b=b,
        resultado=resultado
    )


# ==========================================
# EXECUTAR SERVIDOR
# ==========================================

if __name__ == '__main__':

    inicializar_administrador()

    app.run(
        host='0.0.0.0',
        port=5002,
        debug=False
    )