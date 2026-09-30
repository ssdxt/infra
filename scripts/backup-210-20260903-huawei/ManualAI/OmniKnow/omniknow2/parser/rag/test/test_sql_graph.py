# dialect = "sqlite"

# prompt = """You are now a {dialect} data analyst, and you are given a database schema as follows:

# 【Schema】
# {db_schema}

# 【Question】
# {question}

# 【Evidence】
# {evidence}

# Please read and understand the database schema carefully, and generate an executable SQL based on the user's question and evidence. The generated SQL is protected by ```sql and ```.
# """.format(dialect=dialect, question=question, db_schema=mschema_str, evidence=evidence)


from sqlalchemy import create_engine
from schema_engine import SchemaEngine