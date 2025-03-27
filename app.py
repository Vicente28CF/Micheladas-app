from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from flask_mysqldb import MySQL
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired
from decimal import Decimal
from flask_wtf.csrf import CSRFProtect
import time

app = Flask(__name__)
app.secret_key = "micheladas-secret-key"

# Configuración de MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'flores28'
app.config['MYSQL_DB'] = 'negocio_micheladas'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
csrf = CSRFProtect(app)

# Modelo de usuario
class User(UserMixin):
    def __init__(self, id, nombre, contrasena):
        self.id = id
        self.nombre = nombre
        self.contrasena = contrasena

@login_manager.user_loader
def load_user(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, nombre, contrasena FROM usuarios WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        if user:
            return User(user['id'], user['nombre'], user['contrasena'])
        return None
    except Exception as e:
        print(f"Error en load_user: {e}")
        return None

class LoginForm(FlaskForm):
    username = StringField('Nombre de usuario', validators=[InputRequired()])
    password = PasswordField('Contraseña', validators=[InputRequired()])
    submit = SubmitField('Iniciar sesión')

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id, nombre, contrasena FROM usuarios WHERE nombre = %s", (username,))
            user = cur.fetchone()
            cur.close()
            if user and bcrypt.check_password_hash(user["contrasena"], password):
                login_user(User(user["id"], user["nombre"], user["contrasena"]))
                flash("Inicio de sesión exitoso")
                return redirect(url_for("home"))
            else:
                flash("Credenciales incorrectas. Intenta nuevamente.")
        except Exception as e:
            print(f"Error en login: {e}")
            flash("Ocurrió un error al iniciar sesión. Intenta nuevamente.")
    return render_template("login.html", form=form)

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    flash("Sesión cerrada exitosamente", "success")  # Muestra el mensaje primero
    
    # Espera 2 segundos para que el usuario vea el mensaje
    time.sleep(2)
    
    logout_user()  # Luego cierra la sesión
    return redirect(url_for("login"))  # Finalmente redirige

@app.route('/')
@login_required
def home():
    client_type = request.args.get('client_type', 'clientes')  # Default a clientes
    
    try:
        cur = mysql.connection.cursor()
        
        if client_type == 'mesas':
            cur.execute("SELECT * FROM mesas ORDER BY numero")
            items = cur.fetchall()
            template_data = {'items': items, 'client_type': client_type}
        
        elif client_type == 'pedidos':
            cur.execute("""
                SELECT p.*, c.nombre as cliente_nombre, m.numero as mesa_numero 
                FROM pedidos p
                LEFT JOIN clientes c ON p.cliente_id = c.id
                LEFT JOIN mesas m ON p.mesa_id = m.id
                WHERE p.estado != 'completado'
                ORDER BY p.fecha DESC
            """)
            pedidos = cur.fetchall()
            template_data = {'pedidos': pedidos, 'client_type': client_type}
        
        else:  # clientes
            cur.execute("SELECT * FROM clientes ORDER BY nombre")
            clientes = cur.fetchall()
            template_data = {'items': clientes, 'client_type': 'clientes'}
        
        cur.close()
        return render_template('home.html', **template_data)
    
    except Exception as e:
        print(f"Error en home: {e}")
        flash("Ocurrió un error al cargar la página.")
        return redirect(url_for("login"))

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register_client():
    if request.method == 'GET':
        return render_template('register_client.html')
    
    try:
        client_type = request.form.get('client_type')
        
        if client_type == 'mesa':
            numero = request.form.get('mesa-number')
            capacidad = request.form.get('mesa-capacity')
            
            if not numero or not capacidad:
                flash('Todos los campos son obligatorios para registrar una mesa', 'error')
                return redirect(url_for('register_client'))
            
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO mesas (numero, capacidad) VALUES (%s, %s)", 
                       (numero, capacidad))
            mysql.connection.commit()
            cur.close()
            flash('Mesa registrada exitosamente!', 'success')
            return redirect(url_for('home', client_type='mesas'))
        
        elif client_type == 'cliente':
            nombre = request.form.get('cliente-name')
            
            if not nombre:
                flash('El nombre del cliente es obligatorio', 'error')
                return redirect(url_for('register_client'))
            
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO clientes (nombre) VALUES (%s)", (nombre,))
            mysql.connection.commit()
            cur.close()
            flash('Cliente registrado exitosamente!', 'success')
            return redirect(url_for('home', client_type='clientes'))
        
        elif client_type == 'pedido':
            cliente_nombre = request.form.get('pedido-cliente')
            direccion = request.form.get('pedido-direccion')
            descripcion = request.form.get('pedido-desc')
            notas = request.form.get('pedido-notas')
            
            if not cliente_nombre or not direccion or not descripcion:
                flash('Todos los campos marcados como obligatorios deben llenarse', 'error')
                return redirect(url_for('register_client'))
            
            cur = mysql.connection.cursor()
            
            # Registrar cliente si no existe
            cur.execute("INSERT INTO clientes (nombre) VALUES (%s) ON DUPLICATE KEY UPDATE nombre=nombre", 
                       (cliente_nombre,))
            
            # Obtener ID del cliente
            cur.execute("SELECT id FROM clientes WHERE nombre = %s", (cliente_nombre,))
            cliente_id = cur.fetchone()['id']
            
            # Registrar pedido con total temporal 0 (se actualizará después)
            cur.execute("""
                INSERT INTO pedidos 
                (empleado_id, cliente_id, direccion, descripcion, notas, total, tipo, estado)
                VALUES (%s, %s, %s, %s, %s, 0, 'domicilio', 'pendiente')
            """, (current_user.id, cliente_id, direccion, descripcion, notas))
            
            mysql.connection.commit()
            cur.close()
            flash('Pedido registrado exitosamente!', 'success')
            return redirect(url_for('home', client_type='pedidos'))
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error en register_client: {e}")
        flash(f"Ocurrió un error al registrar: {str(e)}", 'error')
        return redirect(url_for('register_client'))

@app.route('/client/<int:client_id>', methods=['GET'])
@login_required
def client_orders(client_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM clientes WHERE id = %s", (client_id,))
        client = cur.fetchone()
        
        if not client:
            flash('Cliente no encontrado.')
            return redirect(url_for('home'))
        
        cur.execute("""
            SELECT p.* FROM pedidos p
            WHERE p.cliente_id = %s AND p.estado != 'completado'
            ORDER BY p.fecha DESC
        """, (client_id,))
        orders = cur.fetchall()
        cur.close()
        
        return render_template('client_orders.html', 
                             client=client, 
                             orders=orders)
    
    except Exception as e:
        print(f"Error en client_orders: {e}")
        flash("Ocurrió un error al cargar los pedidos.")
        return redirect(url_for('home'))

@app.route('/complete_order/<int:order_id>', methods=['POST'])
@login_required
def complete_order(order_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE pedidos 
            SET estado = 'completado' 
            WHERE id = %s
        """, (order_id,))
        mysql.connection.commit()
        flash('Pedido marcado como completado!')
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error en complete_order: {e}")
        flash("Ocurrió un error al completar el pedido.")
    return redirect(url_for('home', client_type='pedidos'))

@app.route('/create_order/<int:table_id>', methods=['GET'])
@login_required
def create_order(table_id):
    try:
        cur = mysql.connection.cursor()
        
        # Verificar que la mesa existe
        cur.execute("SELECT * FROM mesas WHERE id = %s", (table_id,))
        mesa = cur.fetchone()
        
        if not mesa:
            flash('Mesa no encontrada')
            return redirect(url_for('home', client_type='mesas'))
        
        # Renderizar formulario de pedido para mesa
        return render_template('create_order.html', mesa=mesa)
    
    except Exception as e:
        print(f"Error en create_order: {e}")
        flash("Error al crear pedido")
        return redirect(url_for('home', client_type='mesas'))

if __name__ == '__main__':
    app.run(debug=True)