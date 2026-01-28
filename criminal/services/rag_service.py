import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from .store import get_vector_store

load_dotenv()


def get_retriever():
    vector_store = get_vector_store()
    return vector_store.as_retriever(search_kwargs={"k": 3})


def get_chain():
    retriever = get_retriever()
    llm = ChatOpenAI(model_name="gpt-5-mini", api_key=os.getenv("OPENAI_API_KEY"))
    prompt = ChatPromptTemplate.from_template(
        """
            당신은 **형사법** 법령 검색 도움 봇입니다.
            일상적인 대화라면 일상적인 대화로 답변하세요.
            일상적인 대화 또는 형사법에 대한 질문이 아니라면 관련 법령을 검색할 수 없다고 답변하고 전문가의 도움을 받기를 제안하세요.
            제공된 {context}를 바탕으로 사용자의 {question}에 답변해 주세요.
            Question이 **형사법**에 해당하지 않는 법령에 대한 질문이라면 관련 법령을 검색할 수 없다고 답변하고 전문가의 도움을 받기를 제안하세요.
            

            **Required Rule**
                1. 일상적인 대화라면 일상적인 대화로 답변하세요.
                2. 형사법에 대한 답변이라면 반드시 답변의 근거가 된 참고자료({context})를 포함해야 합니다.
                3. 해당하는 형사법에 대한 {context}가 없을 경우 관련 법령을 검색할 수 없다고 답변하고 전문가의 도움을 받기를 제안하세요.
                4. 질문이 형사법에 관련된 내용이라면 **형사법**에 대한 답변만을 생성해야 합니다.
                5. 당신은 일상대화가 아니고 형사법에 대한 질문에 대해서는 법령에 대한 정보만 제공합니다. 추가 의견이나 조언을 추가하지 않습니다.

            Context:
            {context}

            Question:
            {question}
        """
    )

    def format_str(docs: list) -> str:
        return "\n".join(doc.page_content for doc in docs)

    chain = (
        {"context": retriever | format_str, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain
