import sqlite3
from typing import TypedDict
from google import genai
from google.genai import types
from langgraph.graph import StateGraph,END

import os
from dotenv import load_dotenv
load_dotenv()

client = genai.Client()

db_path='./Chinook_Sqlite.sqlite'


class AgentState(TypedDict):
    user_question:str
    database_schema:str
    sql_query:str
    db_answer:str
    insert_sql:str
    final_answer:str
    error_message:str
    error_count:int


def database_schema(state:AgentState):

    print("taking the database schema....")

    database=sqlite3.connect(db_path)
    cursor=database.cursor()

    cursor.execute("select sql from sqlite_master where type='table' ")


    tables=cursor.fetchall()
    database.close()
    db_schema='\n'.join([table[0] for table in tables if table[0] is not None])

    return{
      "database_schema":db_schema,
      "error_message":"",
      "error_count":0
    }
        

def write_sql(state:AgentState):
    print("the writing node is on.........")

    question=state.get('user_question')
    schema=state.get('database_schema')
    errors=state.get('error_message')

    if errors:

        print('fixing errors......')


        prompt=f"""
        You are an expert SQLite data analyst.
        Here is the schema: {schema}

        The user asked: "{question}"
        IMPORTANT: When filtering by name (Artist, Album, Track), always use COLLATE NOCASE 
for case-insensitive matching. Example: WHERE AR.Name = 'Joker' COLLATE NOCASE
        Your previous query failed with this error: {errors}
        
        Write a CORRECTED SQLite query. 
        IMPORTANT: Return ONLY the raw SQL string. No markdown formatting (```sql), no explanation.
                """
        

    else:

        print("writing the sqlite query......")
        prompt=f"""
You are an expert SQLite data analyst.
        Here is the schema: {schema}
        The user asked: "{question}"
        
        
        Write a  SQLite query. 
        IMPORTANT: Return ONLY the raw SQL string. No markdown formatting (```sql), no explanation.
        """


    response=client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0)
        )

    raw_sql = response.text.replace("```sql", "").replace("```", "").strip()

    print(f"raw sql query is  {raw_sql}")

    return {
            "sql_query":raw_sql
        }
    



def getting_data(state:AgentState):
    print('the sqlite query is being executed......')


    try:
        conn=sqlite3.connect(db_path)
        cursor=conn.cursor()
        cursor.execute(state.get('sql_query'))

        rows=cursor.fetchall()
        conn.close()

        print(f"system gor the answer with {len(rows)} no of rows")



        return {
            'db_answer':rows
        }
    
    except Exception as e:
        print("there is an error with the sql query....  tracing back...")
        print(f"error message: {e}")

        return{
            'error_message':e,
            "error_count": state.get('error_count', 0) + 1
        }
    


    

def ai_response(state:AgentState):


    print("the ai is writing the answer in a neat way")

    prompt=f"""
     you are friendly data analyst 
     heres the question the user asked :{state.get('user_question')}

    and heres the answer for that query:{state.get('db_answer')}

    write a friendly anf cheerful summary from these 


"""
    response=client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )

    return {
        'final_answer':response.text
    }


# def insert_data(state:AgentState):
#     print("the ai agent can not find the answer from the database..... enter the data you want it to insert..")

#     data=input()
#     schema=state.get('database_schema')
    
#     prompt=f"""
#     You are a strict SQLite assistant. 
#     DATABASE SCHEMA: {schema}
    
#     USER DATA TO ADD: "{data}"
#     Capitalize names properly (e.g., 'joker' → 'Joker') before inserting.
    
#     TASK:
#     1. Write a SQL script to insert the Artist, then the Album, then the Tracks.
#     2. IMPORTANT: The 'Track' table has NOT NULL constraints on 'MediaTypeId' and 'GenreId'. 
#        Use '1' for 'MediaTypeId' and '1' for 'GenreId' as defaults.
#     3. Use '1' for 'Milliseconds' and '0.99' for 'UnitPrice' if not specified.
#     4. ONLY use the data provided by the user.
#     """

#     response=client.models.generate_content(
#         model='gemini-2.5-flash',
#         contents=prompt,
#         config=types.GenerateContentConfig(temperature=0.0)
#     )
#     raw_text=response.text
#     if "INSERT" in raw_text:
#         sql_command = raw_text[raw_text.find("INSERT"):]
#     elif "PRAGMA" in raw_text:
#         sql_command = raw_text[raw_text.find("PRAGMA"):]
#     else:
#         sql_command = raw_text

#     sql_command=sql_command.replace("```sql", "").replace("```", "").strip()
#     print(sql_command)

#     try:
#         conn=sqlite3.connect(db_path)
#         cursor=conn.cursor()
#         cursor.executescript(sql_command) # can handle multiple sql queries at once
#         conn.commit()
#         rows=cursor.fetchall()
#         conn.close()

#         print("the data was successfully inserted into the database!!!")
#         return{
#             'final_answer':'Data inserted successfully'
#         }

#     except Exception as e:
#         print(f"some error occured....{e}  ")
#         return{
#             'final_answer':'Data insertion failed'
#         }

    







def router_after_execution(state:AgentState):

    print("the ai agent is running")

    error=state.get("error_message")
    error_number=state.get('error_count')


    if error:
        if error_number >=3:
         return "fail"
        return 'fix_sql'
    # if not state.get('db_answer') or state.get('db_answer')==[]:
    #     return "write_data"

    
    print("-> [MANAGER]: Success! Sending data to Reporter.")
    return "success"
    

workflow=StateGraph(AgentState)

workflow.add_node("setup",database_schema)
workflow.add_node("sql_writer",write_sql)
workflow.add_node("data_from_db",getting_data)
workflow.add_node("response",ai_response)
# workflow.add_node("write_data",insert_data)

workflow.set_entry_point("setup")
workflow.add_edge("setup","sql_writer")
workflow.add_edge("sql_writer","data_from_db")
# workflow.add_edge("write_data",END)
workflow.add_conditional_edges(
    "data_from_db",
    router_after_execution,
    {
        "fix_sql":"sql_writer",
        "fail":"response",
        "success":"response",
        # "write_data":"write_data"

}
)

workflow.add_edge("response",END)


app=workflow.compile()


def run_ai_agent(question:str):
    initial_question={'user_question':question}

    final_state=app.invoke(initial_question)

    return{
        'sql':final_state.get('sql_query'),
        'answer':final_state.get('final_answer')

    }



