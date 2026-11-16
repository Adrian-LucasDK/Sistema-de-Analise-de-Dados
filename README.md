# Sistema de Análise de Dados

Sistema web em Python/Flask para importar arquivos CSV, calcular estatísticas e visualizar gráficos em uma rede local (LAN), com múltiplos usuários e administração de contas.

## Recursos
- Login e sessão individual.
- Perfis `admin` e `user`.
- Administrador pode criar usuários e administradores, além de excluir contas.
- Proteções: não permite excluir a própria conta nem o último administrador.
- Importação de arquivos CSV (até 20 MB).
- Dashboard com total de registros, colunas, valores ausentes e campos numéricos.
- Estatísticas: média, mediana, mínimo, máximo e desvio padrão.
- Prévia dos primeiros registros.
- Gráfico de distribuição (histograma) e gráfico de valores.
- Banco SQLite; os arquivos importados ficam na pasta `uploads`.

## Requisitos
- Windows 10/11 ou Linux.
- Python 3.10 ou superior.
- Computadores conectados à mesma rede local.

## Instalação no computador servidor
1. Instale o Python e marque **Add Python to PATH** durante a instalação.
2. Extraia a pasta do projeto.
3. Instale o `pip install -r requirements.txt`
4. Execute `app.py` (Windows). 
5. No computador servidor, abra `http://127.0.0.1:5000`.

## Acesso pelos outros computadores
1. Descubra o IPv4 do computador servidor executando `ipconfig` no Prompt de Comando.
2. Procure o endereço IPv4 da conexão ativa, por exemplo `192.168.0.105`.
3. Nos demais computadores da mesma rede, acesse `http://192.168.0.105:5000` (substitua pelo IP real).
4. Se o Firewall do Windows perguntar, permita o Python em **redes privadas**. Se não aparecer, crie uma regra de entrada TCP para a porta `5000`, restrita à rede privada.

## Primeiro acesso
- Usuário: `admin`
- Senha: `admin123`

**Altere a senha inicial assim que possível.** Nesta versão inicial, a troca de senha pode ser feita alterando a senha no banco ou adicionando a funcionalidade de redefinição. Não exponha a aplicação diretamente à internet.

## Formato do CSV
- A primeira linha deve conter os nomes das colunas.
- Use vírgula ou ponto e vírgula como separador; a detecção é automática.
- Colunas numéricas devem conter números reconhecíveis pelo Pandas.
- Exemplo:

```csv
Produto,Categoria,Vendas,Quantidade
Notebook,Eletrônicos,4500,2
Mouse,Periféricos,120,5
Teclado,Periféricos,250,3
Monitor,Eletrônicos,1200,1
```

## Observações
- Todos os usuários autenticados visualizam os conjuntos de dados cadastrados no sistema.
- O banco `database.db` e a pasta `uploads` são criados automaticamente.
- Faça cópias de segurança de `database.db` e `uploads`.
- Para uso real em ambiente corporativo, configure uma `SECRET_KEY` fixa, HTTPS se houver acesso fora da LAN, política de backup e validação dos CSVs conforme a origem dos dados.
