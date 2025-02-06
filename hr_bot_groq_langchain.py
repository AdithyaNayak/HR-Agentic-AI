import os
import sqlite3
import warnings
from langchain.agents import initialize_agent, Tool, AgentType
from langchain_groq import ChatGroq
from langchain.memory import ConversationBufferWindowMemory
from langchain.memory.chat_message_histories import FileChatMessageHistory

warnings.filterwarnings("ignore")

# ----------------------------
# 1. Set Up a Simple HR Database
# ----------------------------
def setup_db():
    """Creates an in-memory SQLite database with a sample employees table."""
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    c.execute("CREATE TABLE employees (employee_id TEXT PRIMARY KEY, leave_balance INTEGER)")
    # Insert sample data.
    c.execute("INSERT INTO employees VALUES ('EMP123', 15)")
    c.execute("INSERT INTO employees VALUES ('EMP456', 10)")
    conn.commit()
    return conn

db_conn = setup_db()

# ----------------------------
# 2. Define the Tools
# ----------------------------
def leave_balance_query(employee_id: str) -> str:
    """Queries the HR database for the leave balance of the given employee."""
    c = db_conn.cursor()
    c.execute("SELECT leave_balance FROM employees WHERE employee_id = ?", (employee_id,))
    row = c.fetchone()
    if row:
        return f"Employee {employee_id} has {row[0]} vacation days remaining."
    else:
        return f"No record found for employee {employee_id}."

def policy_lookup(query: str) -> str:
    """Retrieves an HR policy from a text file."""
    try:
        with open("policies.txt", "r", encoding="utf-8") as f:
            policies = dict(line.strip().split(": ", 1) for line in f if ": " in line)
        return policies.get(query.lower(), "Policy not found. Please ask about vacation, healthcare, promotion, onboarding, or benefits.")
    except FileNotFoundError:
        return "Policy file not found. Please ensure policies.txt exists."

tools = [
    Tool(
        name="Leave Balance Check",
        func=lambda input: leave_balance_query(input.split()[-1]),
        description=(
            "Useful for checking an employee's leave balance by accessing the HR database. "
            "When a user says something like 'leave balance EMP123', this tool should be called."
        )
    ),
    Tool(
        name="HR Policy Lookup",
        func=policy_lookup,
        description=(
            "Useful for retrieving HR policies. When a user asks about policies such as 'vacation', 'healthcare', "
            "or 'promotion', this tool should be called. The input should be a single keyword."
        )
    )
]

# ----------------------------
# 3. Set Up Persistent Memory
# ----------------------------
# We use FileChatMessageHistory to persist conversation history to a file,
# and wrap it with ConversationBufferWindowMemory so that the agent can use the history.
memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    return_messages=True,
    chat_memory=FileChatMessageHistory("chat_history.txt")
)

# ----------------------------
# 4. Initialize the Groq LLM and the Agent with a System Prompt
# ----------------------------
# The system prompt instructs HRBot to be friendly and professional, and to remember the user's name if provided.
agent_kwargs = {
    "prefix": (
        "You are HRBot, a friendly and professional HR assistant. "
        "Your responsibilities include answering questions about company policies, leave balances, onboarding, benefits, etc. "
        "If a user provides their name (for example, 'my name is adi'), remember it and address them by name in future responses. "
        "Don't answer any questions that are out of context or inappropriate."
        "Use the available tools when appropriate."
    )
}

llm = ChatGroq(
    temperature=0.7,
    model_name="llama3-70b-8192"
)

# Initialize the agent with our tools, Groq LLM, system prompt, and persistent memory.
agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    agent_kwargs=agent_kwargs,
    memory=memory
)

# ----------------------------
# 5. Run the Chatbot
# ----------------------------
def hr_chatbot():
    print("HRBot: Hello! I'm your HR assistant. How can I help you today?")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("HRBot: Thank you for using HR services!")
            break

        # The agent processes the query using the persistent memory.
        response = agent.run(user_input)
        print(f"HRBot: {response}")

if __name__ == "__main__":
    hr_chatbot()
