from flask import Flask, render_template, request, redirect, send_from_directory, url_for, flash, jsonify
import sqlite3
import os
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import locale 

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "danger"


try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR')
    except locale.Error:
        try:
             locale.setlocale(locale.LC_ALL, 'portuguese_brazil')
        except locale.Error:
            pass 
        
def formatar_moeda(valor):
    if valor is None:
        return "R$ 0,00"
    try:
        valor_float = float(valor)
    except (TypeError, ValueError):
        return "R$ Inválido" 
        
    return locale.currency(valor_float, symbol=True, grouping=True)

app.jinja_env.filters['moeda'] = formatar_moeda


@app.route('/images/<path:filename>')
def images(filename):
    return send_from_directory('images', filename)

def conexao():
    con = sqlite3.connect('database.db')
    con.row_factory = sqlite3.Row
    return con

class User(UserMixin):
    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

    @staticmethod
    def get(user_id):
        con = conexao()
        cur = con.cursor()
        cur.execute("SELECT id, username, email, password_hash FROM users WHERE id = ?", (user_id,))
        user_data = cur.fetchone()
        con.close()
        if user_data:
            return User(**user_data)
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if not username or not email or not password:
            flash('Todos os campos são obrigatórios.', 'danger')
            return render_template('registro.html', request=request)
        con = conexao()
        cur = con.cursor()
        cur.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cur.fetchone():
            flash('Nome de usuário ou email já cadastrado.', 'danger')
            con.close()
            return render_template('registro.html', request=request)
        password_hash = generate_password_hash(password)
        try:
            cur.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (username, email, password_hash))
            con.commit()
            flash('Conta criada com sucesso! Faça login para continuar.', 'success')
            return redirect(url_for('login'))
        except sqlite3.Error as e:
            flash(f'Erro ao registrar usuário: {e}', 'danger')
        finally:
            con.close()
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user_identifier = request.form['user_identifier']
        password = request.form['password']
        remember = True if request.form.get('remember') else False
        con = conexao()
        cur = con.cursor()
        cur.execute("SELECT id, username, email, password_hash FROM users WHERE username = ? OR email = ?", (user_identifier, user_identifier))
        user_data = cur.fetchone()
        con.close()
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(**user_data)
            login_user(user, remember=remember)
            flash(f'Bem-vindo de volta, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Nome de usuário, email ou senha inválidos.', 'danger')
    return render_template('login.html', request=request)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado com sucesso.', 'info')
    return redirect(url_for('login'))

@app.route('/search_autocomplete', methods=['GET'])
@login_required
def search_autocomplete():
    con = conexao()
    cur = con.cursor()
    query = request.args.get('query', '')
    if query:
        cur.execute("SELECT id, nome FROM produtos WHERE nome LIKE ? LIMIT 10", ('%' + query + '%',))
        produtos = [{'id': row['id'], 'nome': row['nome']} for row in cur.fetchall()]
        con.close()
        return jsonify(produtos)
    con.close()
    return jsonify([])

@app.route('/')
@app.route('/index') 
@login_required
def dashboard():
    con = conexao()
    cur = con.cursor()
    
    total_produtos = cur.execute("SELECT COUNT(id) FROM produtos").fetchone()[0]
    total_quantidade = cur.execute("SELECT SUM(quantidade) FROM produtos").fetchone()[0] or 0
    total_valor_estoque = cur.execute("SELECT SUM(quantidade * preco) FROM produtos").fetchone()[0] or 0
    produtos_baixo_estoque = cur.execute("SELECT COUNT(id) FROM produtos WHERE quantidade < 10").fetchone()[0]
    con.close()
    widget_data = {
        'total_produtos': total_produtos,
        'total_quantidade': total_quantidade,
        'total_valor_estoque': total_valor_estoque,
        'produtos_baixo_estoque': produtos_baixo_estoque
    }
  
    return render_template('index.html', widget_data=widget_data)

@app.route('/produtos')
@login_required
def produtos_list():
    con = conexao()
    cur = con.cursor()
    search_query = request.args.get('search', '')

    if search_query:
        cur.execute("SELECT id, nome, quantidade, preco FROM produtos WHERE nome LIKE ? ORDER BY id DESC", (f'%{search_query}%',))
    else:
        cur.execute("SELECT id, nome, quantidade, preco FROM produtos ORDER BY id DESC")
    produtos = cur.fetchall()
    con.close()

    return render_template('produtos_list.html', produtos=produtos, search_query=search_query)


@app.route('/add', methods=('GET', 'POST'))
@login_required
def add():
    if request.method == 'POST':
        nome = request.form['nome']
        quantidade = request.form['quantidade']
        preco = request.form['preco']
        if not nome or not quantidade or not preco:
            flash('Nome, Quantidade e Preço são obrigatórios!', 'danger')
        else:
            con = conexao()
            cur = con.cursor()
            cur.execute("INSERT INTO produtos (nome, quantidade, preco) VALUES (?, ?, ?)", (nome, quantidade, preco))
            con.commit()
            con.close()
            flash(f'Produto "{nome}" adicionado com sucesso.', 'success')
            return redirect(url_for('produtos_list'))
    return render_template('add.html')

def get_produto(id):
    con = conexao()
    cur = con.cursor()
    cur.execute("SELECT id, nome, quantidade, preco FROM produtos WHERE id = ?", (id,))
    produto = cur.fetchone()
    con.close()
    return produto

@app.route('/produto_detalhe/<int:id>')
@login_required
def produto_detalhe(id):
    produto = get_produto(id)
    if produto is None:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('produtos_list'))
    return render_template('produto_detalhe.html', produto=produto)

@app.route('/edit/<int:id>', methods=('GET', 'POST'))
@login_required
def edit(id):
    produto = get_produto(id)
    if produto is None:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('produtos_list'))
    if request.method == 'POST':
        nome = request.form['nome']
        quantidade = request.form['quantidade']
        preco = request.form['preco']
        if not nome or not quantidade or not preco:
            flash('Nome, Quantidade e Preço são obrigatórios!', 'danger')
        else:
            con = conexao()
            cur = con.cursor()
            cur.execute("UPDATE produtos SET nome = ?, quantidade = ?, preco = ? WHERE id = ?", (nome, quantidade, preco, id))
            con.commit()
            con.close()
            flash(f'Produto "{nome}" atualizado com sucesso.', 'success')
            return redirect(url_for('produtos_list'))
    return render_template('edit.html', produto=produto)

@app.route('/delete/<int:id>', methods=('GET', 'POST'))
@login_required
def delete(id):
    con = conexao()
    cur = con.cursor()
    cur.execute("SELECT nome FROM produtos WHERE id=?", (id,))
    produto_nome = cur.fetchone()
    if produto_nome:
        produto_nome = produto_nome[0]
        cur.execute("DELETE FROM produtos WHERE id=?", (id,))
        con.commit()
        flash(f'Produto "{produto_nome}" deletado com sucesso.', 'info')
    else:
        flash('Produto não encontrado.', 'danger')
    con.close()
    return redirect(url_for('produtos_list'))


if __name__ == '__main__':
    with app.app_context():
        con = conexao()
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                preco REAL NOT NULL
            );
        """)
        con.commit()
        con.close()
    app.run(debug=True)