"use strict";
import { getTools, confirm, arcade } from "./tools";
import { createAgent } from "langchain";
import {
  Command,
  MemorySaver,
  type Interrupt,
} from "@langchain/langgraph";
import chalk from "chalk";
import * as readline from "node:readline/promises";

// configure your own values to customize your agent

// The Arcade User ID identifies who is authorizing each service.
const arcadeUserID = process.env.ARCADE_USER_ID;
if (!arcadeUserID) {
  throw new Error("Missing ARCADE_USER_ID. Add it to your .env file.");
}
// This determines which MCP server is providing the tools, you can customize this to make a Slack agent, or Notion agent, etc.
// all tools from each of these MCP servers will be retrieved from arcade
const toolkits=['Imgflip'];
// This determines isolated tools that will be
const isolatedTools=[];
// This determines the maximum number of tool definitions Arcade will return
const toolLimit = 100;
// This prompt defines the behavior of the agent.
const systemPrompt = `# AI Meme Generator Agent

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

This structure allows the AI agent to be adaptable and efficient in creating memes based on user input, using the tools available effectively.`;
// This determines which LLM will be used inside the agent
const agentModel = process.env.OPENAI_MODEL;
if (!agentModel) {
  throw new Error("Missing OPENAI_MODEL. Add it to your .env file.");
}
// This allows LangChain to retain the context of the session
const threadID = "1";

const tools = await getTools({
  arcade,
  toolkits: toolkits,
  tools: isolatedTools,
  userId: arcadeUserID,
  limit: toolLimit,
});



async function handleInterrupt(
  interrupt: Interrupt,
  rl: readline.Interface
): Promise<{ authorized: boolean }> {
  const value = interrupt.value;
  const authorization_required = value.authorization_required;
  const hitl_required = value.hitl_required;
  if (authorization_required) {
    const tool_name = value.tool_name;
    const authorization_response = value.authorization_response;
    console.log("⚙️: Authorization required for tool call", tool_name);
    console.log(
      "⚙️: Please authorize in your browser",
      authorization_response.url
    );
    console.log("⚙️: Waiting for you to complete authorization...");
    try {
      await arcade.auth.waitForCompletion(authorization_response.id);
      console.log("⚙️: Authorization granted. Resuming execution...");
      return { authorized: true };
    } catch (error) {
      console.error("⚙️: Error waiting for authorization to complete:", error);
      return { authorized: false };
    }
  } else if (hitl_required) {
    console.log("⚙️: Human in the loop required for tool call", value.tool_name);
    console.log("⚙️: Please approve the tool call", value.input);
    const approved = await confirm("Do you approve this tool call?", rl);
    return { authorized: approved };
  }
  return { authorized: false };
}

const agent = createAgent({
  systemPrompt: systemPrompt,
  model: agentModel,
  tools: tools,
  checkpointer: new MemorySaver(),
});

async function streamAgent(
  agent: any,
  input: any,
  config: any
): Promise<Interrupt[]> {
  const stream = await agent.stream(input, {
    ...config,
    streamMode: "updates",
  });
  const interrupts: Interrupt[] = [];

  for await (const chunk of stream) {
    if (chunk.__interrupt__) {
      interrupts.push(...(chunk.__interrupt__ as Interrupt[]));
      continue;
    }
    for (const update of Object.values(chunk)) {
      for (const msg of (update as any)?.messages ?? []) {
        console.log("🤖: ", msg.toFormattedString());
      }
    }
  }

  return interrupts;
}

async function main() {
  const config = { configurable: { thread_id: threadID } };
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log(chalk.green("Welcome to the chatbot! Type 'exit' to quit."));
  while (true) {
    const input = await rl.question("> ");
    if (input.toLowerCase() === "exit") {
      break;
    }
    rl.pause();

    try {
      let agentInput: any = {
        messages: [{ role: "user", content: input }],
      };

      // Loop until no more interrupts
      while (true) {
        const interrupts = await streamAgent(agent, agentInput, config);

        if (interrupts.length === 0) {
          break; // No more interrupts, we're done
        }

        // Handle all interrupts
        const decisions: any[] = [];
        for (const interrupt of interrupts) {
          decisions.push(await handleInterrupt(interrupt, rl));
        }

        // Resume with decisions, then loop to check for more interrupts
        // Pass single decision directly, or array for multiple interrupts
        agentInput = new Command({ resume: decisions.length === 1 ? decisions[0] : decisions });
      }
    } catch (error) {
      console.error(error);
    }

    rl.resume();
  }
  console.log(chalk.red("👋 Bye..."));
  process.exit(0);
}

// Run the main function
main().catch((err) => console.error(err));