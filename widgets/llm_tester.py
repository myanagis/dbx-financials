from openai import OpenAI
import streamlit as st


from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import MarkdownNodeParser, SimpleNodeParser

from llama_index.core.schema import Document, TextNode
from llama_index.core.response.notebook_utils import display_source_node

##############################################

import os
from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

## SETTINGS

DEFAULT_PROMPT:str = """
You are a helpful assistant. You are given the following context information and a question. 
Answer the question based on the context only. If you cannot answer based on the context, say "I don't know."

<context>

Question: <user query>
Answer:
"""

MODEL = "gpt-3.5-turbo"

## FUNCTIONS 
def answer_question(user_question: str, input_context: str) -> str:
    prompt = DEFAULT_PROMPT.replace("<context>", input_context).replace("<user query>", user_question)
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return completion.choices[0].message.content.strip()

def print_nodes(nodes):
    # Print out prettily
    for i, node in enumerate(nodes):
        with st.expander("Chunk"):
            #st.text("=========================================")
            st.caption(f"Metadata:")
            for k, v in node.metadata.items():
                st.caption(f"  - {k}: {v}")
            st.caption(f"Relationships: {node.relationships}")
            st.caption(f"Chunk {i} — {len(node.text)} characters, {len(node.text.split())} words") # , {count_tokens(node.text)} tokens")
            st.divider()
            st.text(f"{node.text}")
            #print(node)
            #print(f"Summary: {node.metadata['summary']}")

def parse_markdown_documents(documents):
    parser = MarkdownNodeParser.from_defaults()
    nodes = parser.get_nodes_from_documents(documents)
    return nodes

def parse_document_by_delimiter(documents: list[Document], delimiter: str):
    for document in documents:
        parts = document.text.split(delimiter)
        nodes = []
        for part in parts:
            cleaned = part.strip()
            if cleaned:
                nodes.append(TextNode(text=cleaned, metadata=document.metadata))
    return nodes

def parse_nodes_by_text_delimiter(nodes, delimiter:str):
    new_nodes = []
    for node in nodes:
        parts = node.text.split(delimiter)
        for part in parts:
            part = part.strip()
            if part:
                # TODO: do we preserve the RELATIONSHIP? or other node info??
                new_nodes.append(TextNode(text=part, metadata=node.metadata))
    return new_nodes

def remove_text_from_nodes(nodes, text_to_remove:str):
    for node in nodes:
        node.text = node.text.replace(text_to_remove, "")
    return nodes

def summarize_text(text: str, summarization_prompt:str) -> str:
    prompt = summarization_prompt.replace("<contents>", text)
    
    client = OpenAI(api_key=OPENAI_API_KEY)

    # TODO: use prompt
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return completion.choices[0].message.content.strip()

def add_summaries_to_nodes(nodes, summarization_prompt:str):
    for node in nodes:
        node_text = node.text
        node_summary = summarize_text(node_text, summarization_prompt)
        node.text = f"[Summary: {node_summary}]\n\n{node_text}"
    return nodes

def merge_in_extra_metadata(nodes, extra_metadata:dict):
    for node in nodes:
        node.metadata.update(extra_metadata)
    return nodes


##################
# Embedding


from llama_index.retrievers.bm25 import BM25Retriever
import Stemmer

# We can pass in the index, docstore, or list of nodes to create the retriever
def embed_nodes_to_bm25_retriever(nodes):
    bm25_retriever = BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=3, # TODO: maybe make a parameter

        # Optional: We can pass in the stemmer and set the language for stopwords
        # This is important for removing stopwords and stemming the query + text
        # The default is english for both
        stemmer=Stemmer.Stemmer("english"),
        language="english",
    )
    return bm25_retriever

#####################################
#### CONSTANTS
#### 


SUMMARIZATION_PROMPT = """
You are helping build a document map of a 10-K filing. Given the excerpt below, identify what kind of content it contains — e.g., whether it includes financial statements, business descriptions, risk factors, or legal disclosures. Do not summarize specific numbers or facts.

Write a single-sentence summary that briefly describes the type of material and its purpose or structure.

Contents:
<contents>
"""





#################################
### Display
#################################

st.title("LLM Tester")


##########
### Inputs

input_files = ["data/silver/sec_edgar/AVY_10K_feb2025_subset_with_summaries.md"] #TODO: make path variable and work better

extra_metadata = {
    "ticker": "AVY",
    "form": "10-K",
    "filing_date": "2025-02-26",
    "report_date": "2024-12-28",
    "primary_document": "https://www.sec.gov/Archives/edgar/data/8818/000000881825000003/avy-20241228.htm",
    "accession_number": "0000008818-25-000003"
}

documents = SimpleDirectoryReader(input_files=input_files).load_data()


#####################################
#### CHUNKING
#### (and post-processing/cleaning)

# Don't parse by markdown first.
#nodes = parse_markdown_documents(documents)
nodes = parse_document_by_delimiter(documents, "\n---\n")

nodes = remove_text_from_nodes(nodes, "\nTable of Contents\n")
#nodes = parse_nodes_by_text_delimiter(nodes, "\n---\n")
nodes = merge_in_extra_metadata(nodes, extra_metadata)

# This summarization should only be done once. Comment this out because it can be expensive (and slow)
#nodes = add_summaries_to_nodes(nodes, summarization_prompt=SUMMARIZATION_PROMPT)

st.header("Chunking")
print_nodes(nodes)


st.divider()

#############
# EMBEDDING

st.header("Embedding")
st.caption("Embedding with BM25 ...")
bm25_retriever = embed_nodes_to_bm25_retriever(nodes)

# BM25 documentation
# https://docs.llamaindex.ai/en/stable/examples/retrievers/bm25_retriever/#bm25-retriever-disk-persistence


#############
# RETRIEVAL

from llama_index.core.response.notebook_utils import display_source_node

st.header("Retrieval")
QUERY = st.text_input("User input:")

# will retrieve context from specific companies

retrieved_nodes = bm25_retriever.retrieve(QUERY)

for node_with_score in retrieved_nodes:
    with st.expander(f"Score: {node_with_score.score}"):
        st.write(node_with_score.node)
    #display_source_node(node_with_score, source_length=5000)




#################################################
# ChatGPT


st.header("Test Prompting")
#user_question = st.text_input("User Question:")
prompt = st.text_area("Prompt:")
input_context = st.text_area("Input Context:")

st.write("Model:")
st.caption(MODEL)
st.write("Default prompt:")
st.caption(DEFAULT_PROMPT)

import json
import pandas as pd

if prompt and input_context:

    st.write("Response:")
    # Answer question does the "<context>" replacing for us
    answer = answer_question(prompt, input_context)
    st.write(answer)

    data = json.loads(answer)

    # Convert to DataFrame
    df = pd.DataFrame(data)

    st.dataframe(df)

#if user_question and input_context:
#    st.write("Response:")
#    st.write(answer_question(user_question, input_context))