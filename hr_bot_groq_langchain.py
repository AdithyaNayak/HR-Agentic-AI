import os
import sqlite3
import warnings
from langchain.agents import initialize_agent, Tool, AgentType
from langchain_groq import ChatGroq

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
# 2. Define the Tools (Including a Database Lookup)
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
    """Retrieves an HR policy from a predefined set of policies."""
    policies = {
        "vacation": "Employees accrue 1.5 vacation days per month.",
        "healthcare": "Medical coverage starts after 30 days of employment.",
        "promotion": "Promotion cycles occur biannually in Q1 and Q3.",
        "onboarding": "New hires complete onboarding in 3 steps: 1) Orientation, 2) Training, 3) Team Integration.",
        "benefits": "Benefits include healthcare, 401(k), and paid time off."
    }
    return policies.get(query.lower(), "Policy not found. Please ask about vacation, healthcare, promotion, onboarding, or benefits.")

# Define tools with detailed descriptions.
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
# 3. Initialize the Groq LLM via LangChain and Set a System Prompt
# ----------------------------
# The Groq LLM integration is provided by langchain-groq.
llm = ChatGroq(
    temperature=0.7,
    model_name="llama3-70b-8192"
)

# Define a system prompt (via a prefix) to set the agent's persona.
agent_kwargs = {
    "prefix": (
        "You are HRBot, a friendly and professional HR assistant. "
        "Your tasks include answering employee questions about company policies, leave balances, onboarding, and benefits. "
        "When needed, use the available tools to fetch real data from the HR database."
    )
}

# Initialize the agent using a Zero-Shot React agent so that it can automatically decide when to call a tool.
agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    agent_kwargs=agent_kwargs
)

# ----------------------------
# 4. Run the Chatbot
# ----------------------------
def hr_chatbot():
    print("HRBot: Hello! I'm your HR assistant. How can I help you today?")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("HRBot: Thank you for using HR services!")
            break

        # The agent automatically decides whether to call a tool or answer directly.
        response = agent.run(user_input)
        print(f"HRBot: {response}")

if __name__ == "__main__":
    hr_chatbot()
