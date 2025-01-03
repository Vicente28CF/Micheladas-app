from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Email

import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
app.secret_key = "micheladas-secret-key"

# Inicializar Flask-Login y Flask-Bcrypt
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"  # Página de login

# Diccionario de usuarios (esto debe ser reemplazado con una base de datos real)
users = {
    "Yesenia17": {
        "password_hash": bcrypt.generate_password_hash("admin123").decode("utf-8"),
        "username": "admin"
    }
}

# Estructura para almacenar clientes y pedidos en memoria
data = {
    "clients": {},  # Estructura: {"client_id": {"name": "Nombre", "phone": "Tel", "orders": []}}
    "current_id": 1
}

# Modelo de usuario


class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

# Crear el formulario de login usando WTForms


class LoginForm(FlaskForm):
    username = StringField('Nombre de usuario', validators=[InputRequired()])
    password = PasswordField('Contraseña', validators=[InputRequired()])
    submit = SubmitField('Iniciar sesión')

# Cargar el usuario


@login_manager.user_loader
def load_user(user_id):
    user_data = users.get(user_id)
    if user_data:
        return User(user_id, user_data["username"], user_data["password_hash"])
    return None

# Ruta para inicio de sesión


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()  # Crear el formulario de inicio de sesión
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        user = users.get(username)

        if user and bcrypt.check_password_hash(user["password_hash"], password):
            # El login fue exitoso
            login_user(User(username, user["username"], user["password_hash"]))
            flash("Inicio de sesión exitoso")
            return redirect(url_for("home"))
        else:
            flash("Credenciales incorrectas. Intenta nuevamente.")

    # Pasar el formulario a la plantilla
    return render_template("login.html", form=form)

# Ruta para cierre de sesión


@app.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    flash("Sesión cerrada exitosamente.")
    return redirect(url_for("login"))

# Ruta principal (protegida por login)


@app.route('/')
@login_required
def home():
    return render_template('home.html', clients=data["clients"])

# Ruta para registrar un cliente


@app.route('/register', methods=['GET', 'POST'])
@login_required
def register_client():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        if name and phone:
            client_id = data["current_id"]
            data["clients"][client_id] = {
                "name": name, "phone": phone, "orders": []}
            data["current_id"] += 1
            flash('Cliente registrado exitosamente!')
            return redirect(url_for('home'))
        else:
            flash('Todos los campos son obligatorios.')
    return render_template('register_client.html')

# Ruta para gestionar pedidos de un cliente


@app.route('/client/<int:client_id>', methods=['GET', 'POST'])
@login_required
def client_orders(client_id):
    client = data["clients"].get(client_id)
    if not client:
        flash('Cliente no encontrado.')
        return redirect(url_for('home'))
    if request.method == 'POST':
        item = request.form['item']
        quantity = request.form['quantity']
        if item and quantity.isdigit():
            client["orders"].append({"item": item, "quantity": int(quantity)})
            flash('Pedido agregado exitosamente!')
        else:
            flash('Datos inválidos. Por favor, revisa los campos.')
    return render_template('client_orders.html', client=client, client_id=client_id)

# Ruta para guardar ventas en Google Sheets


@app.route('/export', methods=['POST'])
@login_required
def export_to_sheet():
    try:
        # Configura el acceso a Google Sheets
        scope = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            "credentials.json", scope)
        client = gspread.authorize(credentials)

        # Abre la hoja de cálculo
        sheet = client.open("Micheladas Ventas").sheet1

        # Exporta los datos
        for client_id, client_data in data["clients"].items():
            for order in client_data["orders"]:
                row = [client_data["name"], client_data["phone"],
                       order["item"], order["quantity"]]
                sheet.append_row(row)

        flash('Datos exportados exitosamente a Google Sheets.')
    except Exception as e:
        flash(f'Error al exportar: {e}')
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
