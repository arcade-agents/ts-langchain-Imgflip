from arcadepy import AsyncArcade
from dotenv import load_dotenv
from google.adk import Agent, Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService, Session
from google_adk_arcade.tools import get_arcade_tools
from google.genai import types
from human_in_the_loop import auth_tool, confirm_tool_usage

import os

load_dotenv(override=True)


async def main():
    app_name = "my_agent"
    user_id = os.getenv("ARCADE_USER_ID")

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    client = AsyncArcade()

    agent_tools = await get_arcade_tools(
        client, toolkits=["Imgflip"]
    )

    for tool in agent_tools:
        await auth_tool(client, tool_name=tool.name, user_id=user_id)

    agent = Agent(
        model=LiteLlm(model=f"openai/{os.environ["OPENAI_MODEL"]}"),
        name="google_agent",
        instruction="# AI Meme Generator Agent

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
        description="An agent that uses Imgflip tools provided to perform any task",
        tools=agent_tools,
        before_tool_callback=[confirm_tool_usage],
    )

    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, state={
            "user_id": user_id,
        }
    )
    runner = Runner(
        app_name=app_name,
        agent=agent,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    async def run_prompt(session: Session, new_message: str):
        content = types.Content(
            role='user', parts=[types.Part.from_text(text=new_message)]
        )
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content.parts and event.content.parts[0].text:
                print(f'** {event.author}: {event.content.parts[0].text}')

    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        await run_prompt(session, user_input)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())