from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

def conexao():
    return sqlite3.connect('database.db')

@app.route('/')
def index():
    con = conexao()
    cur = con.cursor()
    
    # 1. Obtém o termo de busca do parâmetro 'search' na URL
    search_query = request.args.get('search')
    
    if search_query:
        # 2. Query filtrada: usa LIKE para buscar produtos com o termo no nome
        # O '%' permite a busca por parte do nome (busca parcial)
        sql_query = "SELECT * FROM produtos WHERE nome LIKE ?"
        # Adiciona '%' no início e fim do termo para a busca parcial no SQLite
        cur.execute(sql_query, ('%' + search_query + '%',))
    else:
        # 3. Query padrão: seleciona todos os produtos
        sql_query = "SELECT * FROM produtos"
        cur.execute(sql_query)
        
    dados = cur.fetchall()
    con.close()
    
    # 4. Passa o termo de busca para o template manter o campo preenchido
    return render_template('index.html', produtos=dados, search_query=search_query if search_query else '')

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        nome = request.form['nome']
        qtd = request.form['quantidade']
        preco = request.form['preco']
        con = conexao()
        cur = con.cursor()
        cur.execute("INSERT INTO produtos (nome, quantidade, preco) VALUES (?, ?, ?)", (nome, qtd, preco))
        con.commit()
        con.close()
        return redirect('/')
    return render_template('add.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    con = conexao()
    cur = con.cursor()
    if request.method == 'POST':
        nome = request.form['nome']
        qtd = request.form['quantidade']
        preco = request.form['preco']
        cur.execute("UPDATE produtos SET nome=?, quantidade=?, preco=? WHERE id=?", (nome, qtd, preco, id))
        con.commit()
        con.close()
        return redirect('/')
    cur.execute("SELECT * FROM produtos WHERE id=?", (id,))
    produto = cur.fetchone()
    con.close()
    return render_template('edit.html', produto=produto)

@app.route('/delete/<int:id>')
def delete(id):
    con = conexao()
    cur = con.cursor()
    cur.execute("DELETE FROM produtos WHERE id=?", (id,))
    con.commit()
    con.close()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)