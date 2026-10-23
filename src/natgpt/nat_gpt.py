"""NatGPT: a reusable Streamlit app for getting AI answers from data.

Load any CSV file, ask a question in plain English, and a small language
model running on your own machine writes the pandas code needed to answer
it. No API key and no extra software are required, only a pip install.

Install:
    python -m pip install streamlit pandas numpy matplotlib torch transformers

Run:
    python -m streamlit run nat_gpt.py

"""

import builtins
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoTokenizer

APP_NAME = "NatGPT"
APP_TAGLINE = "Ask your data anything in plain English."
ICON_PATH = Path(__file__).with_name("logo.png")
DEFAULT_CSV = "data.csv"

MAX_NEW_TOKENS = 200
SAMPLE_ROWS = 2
MAX_LISTED_VALUES = 15

MODELS = {
    "Lightning (0.5B, about 1 GB)": "Qwen/Qwen2.5-Coder-0.5B-Instruct",
    "Balanced (1.5B, about 3 GB)": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "Smartest (3B, about 6 GB)": "Qwen/Qwen2.5-Coder-3B-Instruct",
}

EXAMPLE_QUESTIONS = [
    "How many rows are in this dataset?",
    "Which columns have the most missing values?",
    "Show the 10 most common values in the first text column.",
]

ALLOWED_BUILTINS = (
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
    "int", "isinstance", "len", "list", "map", "max", "min", "print",
    "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple",
    "zip",
)
SAFE_BUILTINS = {name: getattr(builtins, name) for name in ALLOWED_BUILTINS}

PROMPT_TEMPLATE = """You write pandas code to answer questions about a \
DataFrame named `df`.
{schema}

Rules:
- Reply with ONE ```python code block and nothing else.
- Available names: df, pd, np, plt. No imports, no file access.
- Put the final answer in a variable called `result`.
- For charts use matplotlib (plt) and still set `result`.
- Use the exact column names above. Do not modify df in place.

Example question: How many rows per State, top 3?
```python
result = df['State'].value_counts().head(3)
```
"""


@dataclass
class Turn:
    """One message in the conversation, with any answer attached to it."""

    role: str
    text: str = ""
    code: Optional[str] = None
    result: Any = None
    figure: Any = None


def configure_page() -> None:
    """Set the browser tab title, icon and page layout."""
    page_icon = Image.open(ICON_PATH) if ICON_PATH.exists() else "🔮"
    st.set_page_config(page_title=APP_NAME, page_icon=page_icon,
                       layout="wide")


@st.cache_resource(show_spinner="Loading the model. The first run "
                                "downloads it, so please be patient...")
def load_model(model_id: str):
    """Download (once) and load the tokenizer and model for model_id."""
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=torch.float32
    )
    model.eval()
    return tokenizer, model


@st.cache_data(show_spinner="Reading your data...")
def load_csv(source) -> pd.DataFrame:
    """Read a CSV and convert any column with 'date' in its name."""
    df = pd.read_csv(source)
    for column in df.columns:
        if "date" in column.lower():
            cleaned = df[column].astype(str).str.strip().str.rstrip(".")
            df[column] = pd.to_datetime(
                cleaned, errors="coerce", format="mixed"
            )
    return df


def render_sidebar():
    """Draw the sidebar and return the data source and chosen model id."""
    with st.sidebar:
        if ICON_PATH.exists():
            st.image(str(ICON_PATH), width=110)
        st.title(APP_NAME)
        st.caption(APP_TAGLINE)

        st.subheader("📂 Data")
        upload = st.file_uploader("Upload a CSV", type="csv")
        path = st.text_input("Or type a file path", DEFAULT_CSV)

        st.subheader("🧠 Model")
        label = st.selectbox("Pick a model", list(MODELS))
        st.caption("Bigger models answer better but run slower.")

        st.subheader("💡 Try asking")
        for index, example in enumerate(EXAMPLE_QUESTIONS):
            if st.button(example, key=f"example_{index}"):
                st.session_state["queued_question"] = example

        if st.button("🗑️ Clear chat"):
            st.session_state["history"] = []

    return (upload if upload else path), MODELS[label]


def describe_columns(df: pd.DataFrame) -> str:
    """Summarise columns, types and sample rows for the model prompt."""
    lines = [f"`df` has {len(df)} rows. Columns:"]
    for column in df.columns:
        series = df[column]
        line = f"- {column} ({series.dtype})"
        is_range = (pd.api.types.is_datetime64_any_dtype(series)
                    or pd.api.types.is_numeric_dtype(series))
        if is_range:
            line += f" range {series.min()} to {series.max()}"
        elif series.nunique() <= MAX_LISTED_VALUES:
            line += f" values: {list(series.dropna().unique())}"
        else:
            line += f" e.g. {list(series.dropna().unique()[:4])}"
        lines.append(line)
    lines.append(f"\nFirst {SAMPLE_ROWS} rows:\n"
                 + df.head(SAMPLE_ROWS).to_string())
    return "\n".join(lines)


def extract_code(text: str) -> str:
    """Pull the python code out of a model reply."""
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    return (match.group(1) if match else text).strip()


def generate_code(messages: list, model_id: str, system_prompt: str) -> str:
    """Ask the model for pandas code and return just the code."""
    tokenizer, model = load_model(model_id)
    chat = [{"role": "system", "content": system_prompt}] + messages
    prompt = tokenizer.apply_chat_template(
        chat, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        output = model.generate(
            **inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False
        )
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return extract_code(tokenizer.decode(new_tokens, skip_special_tokens=True))


def run_code(code: str, df: pd.DataFrame):
    """Run generated code on a copy of df and return (result, figure).

    The code gets a trimmed set of builtins and no imports. That blocks
    casual mistakes but it is not a full sandbox, so only use this app on
    your own machine.
    """
    namespace = {
        "df": df.copy(),
        "pd": pd,
        "np": np,
        "plt": plt,
        "__builtins__": SAFE_BUILTINS,
    }
    plt.close("all")
    exec(code, namespace)
    figure = plt.gcf() if plt.get_fignums() else None
    plt.close("all")
    return namespace.get("result"), figure


def answer_question(question: str, df: pd.DataFrame, model_id: str) -> Turn:
    """Generate and run code for a question, showing live progress."""
    system_prompt = PROMPT_TEMPLATE.format(schema=describe_columns(df))
    messages = [{"role": "user", "content": question}]
    progress = st.progress(0, text="Waking up the model...")

    with st.status("Thinking...", expanded=False) as status:
        try:
            load_model(model_id)
            progress.progress(25, text="Writing the code...")
            code = generate_code(messages, model_id, system_prompt)

            progress.progress(65, text="Crunching the numbers...")
            try:
                result, figure = run_code(code, df)
            except Exception as error:
                status.update(label="Fixing a small hiccup...")
                progress.progress(75, text="Trying a fix...")
                messages += [
                    {"role": "assistant",
                     "content": f"```python\n{code}\n```"},
                    {"role": "user",
                     "content": f"That raised: {error!r}. Fix the code."},
                ]
                code = generate_code(messages, model_id, system_prompt)
                result, figure = run_code(code, df)

            progress.progress(100, text="Done!")
            status.update(label="Done", state="complete")
            turn = Turn("assistant", code=code, result=result, figure=figure)
        except Exception as error:
            status.update(label="Something went wrong", state="error")
            turn = Turn("assistant", text=f"Sorry, that did not work: {error}")

    progress.empty()
    return turn


def render_turn(turn: Turn, index: int) -> None:
    """Draw one conversation turn, including tables, charts and code."""
    avatar = "🧑‍💻" if turn.role == "user" else "🔮"
    with st.chat_message(turn.role, avatar=avatar):
        if turn.text:
            st.markdown(turn.text)

        if isinstance(turn.result, (pd.DataFrame, pd.Series)):
            st.dataframe(turn.result, use_container_width=True)
            st.download_button(
                "⬇️ Download as CSV",
                turn.result.to_csv().encode("utf-8"),
                file_name="result.csv",
                mime="text/csv",
                key=f"download_{index}",
            )
        elif turn.result is not None:
            st.write(turn.result)

        if turn.figure is not None:
            st.pyplot(turn.figure)

        if turn.code:
            with st.expander("🔍 See the code that was used"):
                st.code(turn.code, language="python")


def render_dataset_summary(df: pd.DataFrame) -> None:
    """Show quick stats and a preview of the loaded data."""
    missing = df.isna().sum().sum() / max(df.size, 1) * 100
    rows, columns, gaps = st.columns(3)
    rows.metric("Rows", f"{len(df):,}")
    columns.metric("Columns", len(df.columns))
    gaps.metric("Missing values", f"{missing:.1f}%")
    with st.expander("👀 Preview the data"):
        st.dataframe(df.head(50), use_container_width=True)


def main() -> None:
    """Run the app."""
    configure_page()
    source, model_id = render_sidebar()

    st.title(f"🔮 {APP_NAME}")
    st.caption(APP_TAGLINE)

    try:
        df = load_csv(source)
    except Exception as error:
        st.info(f"Upload a CSV or fix the file path in the sidebar. ({error})")
        st.stop()

    render_dataset_summary(df)
    history = st.session_state.setdefault("history", [])

    for index, turn in enumerate(history):
        render_turn(turn, index)

    question = st.chat_input("Ask a question about your data...")
    question = question or st.session_state.pop("queued_question", None)

    if question:
        history.append(Turn("user", text=question))
        render_turn(history[-1], len(history) - 1)
        history.append(answer_question(question, df, model_id))
        render_turn(history[-1], len(history) - 1)


if __name__ == "__main__":
    main()