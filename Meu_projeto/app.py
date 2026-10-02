from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]
        return "Login enviado!"

    return render_template("login.html")


@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route("/imc")
def imc():
    return render_template("imc.html")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)