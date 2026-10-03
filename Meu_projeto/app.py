from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)


# =========================
# PÁGINA INICIAL
# =========================

@app.route('/')
def inicio():
    return render_template('index.html')


# =========================
# PÁGINA SOBRE
# =========================

@app.route('/about')
def about():
    return render_template('about.html')


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        usuario = request.form["usuario"]
        senha = request.form["senha"]

        # Redireciona para o perfil levando os dados pela URL
        return redirect(
            url_for(
                "profile",
                nome=usuario,
                email=usuario
            )
        )

    return render_template("login.html")


# =========================
# PERFIL
# =========================

@app.route('/profile')
def profile():

    nome = request.args.get("nome", "Usuário")
    email = request.args.get("email", "Não informado")
    idade = request.args.get("idade", "Não informado")
    peso = request.args.get("peso", "Não informado")
    altura = request.args.get("altura", "Não informado")

    return render_template(
        'profile.html',
        nome=nome,
        email=email,
        idade=idade,
        peso=peso,
        altura=altura
    )


# =========================
# CALCULADORA DE IMC
# =========================

@app.route("/calcular-imc", methods=["POST"])
def calcular_imc():

    peso = float(request.form["peso"])
    altura = float(request.form["altura"])
    idade = int(request.form["idade"])
    sexo = request.form["sexo"]

    # Envia os dados para a rota exigida pelo professor
    return redirect(
        url_for(
            "imc",
            peso=peso,
            altura=altura,
            idade=idade,
            sexo=sexo
        )
    )


# =========================
# RESULTADO DO IMC
# =========================

@app.route("/imc")
@app.route("/imc/<float:peso>/<float:altura>")
def imc(peso=None, altura=None):

    # Quando entrar em /imc sem dados,
    # apenas abre a página da calculadora.
    if peso is None or altura is None:
        return render_template("imc.html")

    # Recebe idade e sexo pela URL
    idade = request.args.get("idade")
    sexo = request.args.get("sexo")

    # Cálculo do IMC
    valor_imc = peso / (altura ** 2)

    # Classificação do IMC
    if valor_imc < 18.5:
        classificacao = "Magreza"
    elif valor_imc < 25:
        classificacao = "Normal"
    elif valor_imc < 30:
        classificacao = "Sobrepeso"
    else:
        classificacao = "Obesidade"

    # Peso ideal aproximado usando IMC 22
    peso_ideal = 22 * (altura ** 2)

    return render_template(
        "imc.html",
        peso=peso,
        altura=altura,
        idade=idade,
        sexo=sexo,
        imc=round(valor_imc, 2),
        classificacao=classificacao,
        peso_ideal=round(peso_ideal, 2)
    )


# =========================
# EXECUTAR SERVIDOR
# =========================

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5002,
        debug=True
    )