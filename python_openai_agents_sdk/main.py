from agents import (Agent, Runner, AgentHooks, Tool, RunContextWrapper,
                    TResponseInputItem,)
from functools import partial
from arcadepy import AsyncArcade
from agents_arcade import get_arcade_tools
from typing import Any
from human_in_the_loop import (UserDeniedToolCall,
                               confirm_tool_usage,
                               auth_tool)

import globals


class CustomAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.event_counter = 0
        self.display_name = display_name

    async def on_start(self,
                       context: RunContextWrapper,
                       agent: Agent) -> None:
        self.event_counter += 1
        print(f"### ({self.display_name}) {
              self.event_counter}: Agent {agent.name} started")

    async def on_end(self,
                     context: RunContextWrapper,
                     agent: Agent,
                     output: Any) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended with output {output}"
                agent.name} ended"
        )

    async def on_handoff(self,
                         context: RunContextWrapper,
                         agent: Agent,
                         source: Agent) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                source.name} handed off to {agent.name}"
        )

    async def on_tool_start(self,
                            context: RunContextWrapper,
                            agent: Agent,
                            tool: Tool) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}:"
            f" Agent {agent.name} started tool {tool.name}"
            f" with context: {context.context}"
        )

    async def on_tool_end(self,
                          context: RunContextWrapper,
                          agent: Agent,
                          tool: Tool,
                          result: str) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended tool {tool.name} with result {result}"
                agent.name} ended tool {tool.name}"
        )


async def main():

    context = {
        "user_id": os.getenv("ARCADE_USER_ID"),
    }

    client = AsyncArcade()

    arcade_tools = await get_arcade_tools(
        client, toolkits=["Imgflip"]
    )

    for tool in arcade_tools:
        # - human in the loop
        if tool.name in ENFORCE_HUMAN_CONFIRMATION:
            tool.on_invoke_tool = partial(
                confirm_tool_usage,
                tool_name=tool.name,
                callback=tool.on_invoke_tool,
            )
        # - auth
        await auth_tool(client, tool.name, user_id=context["user_id"])

    agent = Agent(
        name="",
        instructions="# AI Meme Generator Agent

## Introduction
This AI agent is designed to create custom memes by leveraging popular templates from Imgflip. It can search for specific meme templates based on user queries or retrieve the most popular memes available. The agent will efficiently utilize the Imgflip API tools to fulfill user requests and produce engaging and humorous meme content.

## Instructions
1. **Understand the User's Request**: Listen carefully to what type of meme the user wants, whether it's a specific theme, topic, or a popular template.
2. **Determine the Source of Meme**:
    - If the user provides a theme or specific meme type, substitute search for the appropriate template using `Imgflip_SearchMemes`.
    - If the user prefers well-known memes without specific preferences, fetch popular templates using `Imgflip_GetPopularMemes`.
3. **Create the Meme**: Once the appropriate template ID has been located, utilize the `Imgflip_CreateMeme` tool to customize the meme by adding the user's specified text.
4. **Provide the Meme URL**: After generating the meme, return the link to the user for sharing or viewing.

## Workflows

### Workflow 1: Creating a Custom Meme from a User Query
1. **Input User Query**: Get the user's request for a specific meme type or theme.
2. **Search for Meme Template**: Use `Imgflip_SearchMemes` with the provided query.
3. **Select a Template**: Choose an appropriate template from the search results.
4. **Create the Meme**: Use `Imgflip_CreateMeme` by providing the selected `template_id` and any specified `top_text` or `bottom_text`.
5. **Return Meme**: Provide the user with a link to the created meme.

### Workflow 2: Generating a Meme from Popular Templates
1. **Request for Popular Memes**: If the user is not specific, retrieve popular meme templates.
2. **Get Popular Memes**: Use `Imgflip_GetPopularMemes` to fetch the latest popular memes.
3. **Select a Template**: Choose a template from the results based on user feedback or preferences.
4. **Create the Meme**: Use `Imgflip_CreateMeme` to customize it with the user's provided text.
5. **Return Meme**: Share the meme's link with the user.

### Workflow 3: Quick Meme Creation with Default Text
1. **User Request for a Simple Meme**: If the user wants a straightforward meme with minimal input, ask for a popular template or theme.
2. **Retrieve Popular Memes**: Use `Imgflip_GetPopularMemes` to get a list of current popular memes.
3. **Choose Template**: Pick one meme template suitable for a generic caption.
4. **Create the Meme Using Default Text**: Use `Imgflip_CreateMeme` to create a meme with standard, humorous text.
5. **Return Meme**: Provide the meme link to the user.

This structure allows the AI agent to be adaptable and efficient in creating memes based on user input, using the tools available effectively.",
        model=os.environ["OPENAI_MODEL"],
        tools=arcade_tools,
        hooks=CustomAgentHooks(display_name="")
    )

    # initialize the conversation
    history: list[TResponseInputItem] = []
    # run the loop!
    while True:
        prompt = input("You: ")
        if prompt.lower() == "exit":
            break
        history.append({"role": "user", "content": prompt})
        try:
            result = await Runner.run(
                starting_agent=agent,
                input=history,
                context=context
            )
            history = result.to_input_list()
            print(result.final_output)
        except UserDeniedToolCall as e:
            history.extend([
                {"role": "assistant",
                 "content": f"Please confirm the call to {e.tool_name}"},
                {"role": "user",
                 "content": "I changed my mind, please don't do it!"},
                {"role": "assistant",
                 "content": f"Sure, I cancelled the call to {e.tool_name}."
                 " What else can I do for you today?"
                 },
            ])
            print(history[-1]["content"])

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())