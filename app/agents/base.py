from typing import Any, List

from decouple import config
from langchain import LLMChain, PromptTemplate
from langchain.agents import AgentType, initialize_agent
from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain.memory.motorhead_memory import MotorheadMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage
from slugify import slugify

from app.datasource.types import (
    VALID_UNSTRUCTURED_DATA_TYPES,
)
from app.models.tools import DatasourceInput
from app.tools import TOOL_TYPE_MAPPING, create_tool
from app.tools.datasource import DatasourceTool, StructuredDatasourceTool
from app.utils.llm import LLM_MAPPING
from app.utils.prisma import prisma
from app.utils.streaming import CustomAsyncIteratorCallbackHandler
from prisma.models import Agent, AgentDatasource, AgentLLM, AgentTool

DEFAULT_PROMPT = (
    "You are a helpful AI Assistant, anwer the users questions to "
    "the best of your ability."
)


class AgentBase:
    def __init__(
        self,
        agent_id: str,
        session_id: str = None,
        enable_streaming: bool = False,
        output_schema: str = None,
        callback: CustomAsyncIteratorCallbackHandler = None,
    ):
        self.agent_id = agent_id
        self.session_id = session_id
        self.enable_streaming = enable_streaming
        self.output_schema = output_schema
        self.callback = callback

    async def _get_tools(
        self, agent_datasources: List[AgentDatasource], agent_tools: List[AgentTool]
    ) -> List:
        tools = []
        for agent_datasource in agent_datasources:
            tool_type = (
                DatasourceTool
                if agent_datasource.datasource.type in VALID_UNSTRUCTURED_DATA_TYPES
                else StructuredDatasourceTool
            )
            metadata = (
                {"datasource_id": agent_datasource.datasource.id, "query_type": "all"}
                if tool_type == DatasourceTool
                else {"datasource": agent_datasource.datasource}
            )
            tool = tool_type(
                metadata=metadata,
                args_schema=DatasourceInput,
                name=slugify(agent_datasource.datasource.name),
                description=agent_datasource.datasource.description,
                return_direct=False,
            )
            tools.append(tool)
        for agent_tool in agent_tools:
            tool_info = TOOL_TYPE_MAPPING.get(agent_tool.tool.type)
            if tool_info:
                tool = create_tool(
                    tool_class=tool_info["class"],
                    name=slugify(agent_tool.tool.name),
                    description=agent_tool.tool.description,
                    metadata=agent_tool.tool.metadata,
                    args_schema=tool_info["schema"],
                    return_direct=agent_tool.tool.returnDirect,
                )
            tools.append(tool)
        return tools

    async def _get_llm(self, agent_llm: AgentLLM, model: str) -> Any:
        if agent_llm.llm.provider == "OPENAI":
            return ChatOpenAI(
                model=LLM_MAPPING[model],
                openai_api_key=agent_llm.llm.apiKey,
                temperature=0,
                streaming=self.enable_streaming,
                callbacks=[self.callback] if self.enable_streaming else [],
                **(agent_llm.llm.options if agent_llm.llm.options else {}),
            )
        if agent_llm.llm.provider == "AZURE_OPENAI":
            return AzureChatOpenAI(
                openai_api_key=config("AZURE_API_KEY"),
                openai_api_base=config("AZURE_API_BASE"),
                openai_api_type=config("AZURE_API_TYPE"),
                openai_api_version=config("AZURE_API_VERSION"),
                deployment_name="gpt-35-turbo-16k",
                temperature=0,
                streaming=self.enable_streaming,
                callbacks=[self.callback] if self.enable_streaming else [],
                **(agent_llm.llm.options if agent_llm.llm.options else {}),
            )

    async def _get_prompt(self, agent: Agent) -> SystemMessage:
        if self.output_schema:
            if agent.prompt:
                content = (
                    f"{agent.prompt}\n\n"
                    "The output should be formatted as a JSON instance "
                    "that conforms to the JSON schema below.\n\n"
                    "Here is the output schema:\n"
                    f"{self.output_schema}"
                )
            else:
                content = (
                    f"{DEFAULT_PROMPT}\n\n"
                    "The output should be formatted as a JSON instance "
                    "that conforms to the JSON schema below.\n\n"
                    "Here is the output schema:\n"
                    f"{self.output_schema}"
                )
        else:
            content = agent.prompt or DEFAULT_PROMPT
        return SystemMessage(content=content)

    async def _get_memory(self) -> MotorheadMemory:
        memory = MotorheadMemory(
            session_id=f"{self.agent_id}-{self.session_id}"
            if self.session_id
            else f"{self.agent_id}",
            memory_key="chat_history",
            url=config("MEMORY_API_URL"),
            return_messages=True,
            output_key="output",
        )
        await memory.init()
        return memory

    async def get_agent(self) -> Any:
        config = await prisma.agent.find_unique_or_raise(
            where={"id": self.agent_id},
            include={
                "llms": {"include": {"llm": True}},
                "datasources": {"include": {"datasource": True}},
                "tools": {"include": {"tool": True}},
            },
        )
        tools = await self._get_tools(
            agent_datasources=config.datasources, agent_tools=config.tools
        )
        llm = await self._get_llm(agent_llm=config.llms[0], model=config.llmModel)
        prompt = await self._get_prompt(agent=config)
        memory = await self._get_memory()

        if len(tools) > 0:
            agent = initialize_agent(
                tools,
                llm,
                agent=AgentType.OPENAI_FUNCTIONS,
                agent_kwargs={
                    "system_message": prompt,
                    "extra_prompt_messages": [
                        MessagesPlaceholder(variable_name="chat_history")
                    ],
                },
                memory=memory,
                return_intermediate_steps=True,
                verbose=True,
            )
            return agent
        else:
            prompt_base = (
                f"{config.prompt.replace('{', '{{').replace('}', '}}')}"
                if config.prompt
                else None
            )
            prompt_base = prompt_base or DEFAULT_PROMPT
            prompt_question = "Question: {input}"
            prompt_history = "History: \n {chat_history}"
            prompt = f"{prompt_base} \n {prompt_question} \n {prompt_history}"
            agent = LLMChain(
                llm=llm,
                memory=memory,
                output_key="output",
                verbose=True,
                prompt=PromptTemplate.from_template(prompt),
            )
        return agent
