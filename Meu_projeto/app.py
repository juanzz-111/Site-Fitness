from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)


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
# LOGIN
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        usuario = request.form['usuario']
        senha = request.form['senha']

        return redirect(
            url_for(
                'profile',
                nome=usuario,
                email=usuario
            )
        )

    return render_template('login.html')


# ==========================================
# PERFIL
# ==========================================

@app.route('/profile')
def profile():

    nome = request.args.get('nome', 'Usuário')
    email = request.args.get('email', 'Não informado')
    idade = request.args.get('idade', 'Não informado')
    peso = request.args.get('peso', 'Não informado')
    altura = request.args.get('altura', 'Não informado')

    return render_template(
        'profile.html',
        nome=nome,
        email=email,
        idade=idade,
        peso=peso,
        altura=altura
    )


# ==========================================
# RECEBER FORMULÁRIO DO IMC
# ==========================================

@app.route('/calcular-imc', methods=['POST'])
def calcular_imc():

    peso = float(request.form['peso'])
    altura = float(request.form['altura'])
    sexo = request.form['sexo']
    idade = int(request.form['idade'])

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

    # Evita erro caso os parâmetros não estejam presentes
    if idade is None:
        idade = 0

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
    #
    # % gordura =
    # 1,20 × IMC + 0,23 × idade
    # - 10,8 × sexo - 5,4
    #
    # sexo = 1 homem
    # sexo = 0 mulher
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

        posicao = 25 + (
            (valor_imc - 18.5) / 6.5
        ) * 25

    elif valor_imc < 30:

        posicao = 50 + (
            (valor_imc - 25) / 5
        ) * 25

    else:

        posicao = 75 + (
            (valor_imc - 30) / 10
        ) * 25

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

    operacao = request.form['operacao']
    numero1 = float(request.form['numero1'])
    numero2 = float(request.form['numero2'])

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
def math(op, a, b):

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

        return 'Operação inválida', 400


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

    app.run(host='0.0.0.0', port=5002, debug=True)