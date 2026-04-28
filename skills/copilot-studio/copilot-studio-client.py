#!/usr/bin/env python3
"""Copilot Studio CLI — create and manage agents via the Power Platform / Dataverse API."""

import argparse
import json
import os
import sys

try:
    import msal
    import requests
except ImportError:
    print("Missing dependencies. Run: pip install msal requests")
    sys.exit(1)


class CopilotStudioClient:
    def __init__(self):
        self.tenant_id = os.environ.get("COPILOT_STUDIO_TENANT_ID")
        self.client_id = os.environ.get("COPILOT_STUDIO_CLIENT_ID")
        self.client_secret = os.environ.get("COPILOT_STUDIO_CLIENT_SECRET")
        self.environment_url = os.environ.get("COPILOT_STUDIO_ENVIRONMENT_URL", "").rstrip("/")

        missing = [
            k for k, v in {
                "COPILOT_STUDIO_TENANT_ID": self.tenant_id,
                "COPILOT_STUDIO_CLIENT_ID": self.client_id,
                "COPILOT_STUDIO_CLIENT_SECRET": self.client_secret,
                "COPILOT_STUDIO_ENVIRONMENT_URL": self.environment_url,
            }.items() if not v
        ]
        if missing:
            print("Missing required environment variables:")
            for var in missing:
                print(f"  {var}")
            sys.exit(1)

        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret,
        )
        scope = f"{self.environment_url}/.default"
        result = app.acquire_token_for_client(scopes=[scope])
        if "access_token" not in result:
            print(f"Authentication failed: {result.get('error_description', result)}")
            sys.exit(1)
        self._token = result["access_token"]
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.environment_url}/api/data/v9.2/{path.lstrip('/')}"

    def _extract_id(self, response: requests.Response) -> str | None:
        entity_id = response.headers.get("OData-EntityId", "")
        if "(" in entity_id:
            return entity_id.split("(")[-1].rstrip(")")
        return None

    # --- Agent operations ---

    def list_agents(self) -> list:
        url = self._url("bots?$select=botid,name,schemaname,statecode&$orderby=name")
        resp = requests.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_agent(self, bot_id: str) -> dict:
        resp = requests.get(self._url(f"bots({bot_id})"), headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def create_agent(self, name: str, schema_name: str, language: str = "en-US", description: str = "") -> dict:
        payload = {"name": name, "schemaname": schema_name, "language": language}
        if description:
            payload["description"] = description
        resp = requests.post(self._url("bots"), headers=self._headers(), json=payload)
        resp.raise_for_status()
        return {"id": self._extract_id(resp), "name": name}

    def update_agent(self, bot_id: str, updates: dict) -> None:
        resp = requests.patch(self._url(f"bots({bot_id})"), headers=self._headers(), json=updates)
        resp.raise_for_status()

    def publish_agent(self, bot_id: str) -> None:
        url = self._url(f"bots({bot_id})/Microsoft.Dynamics.CRM.PublishBotContent")
        resp = requests.post(url, headers=self._headers(), json={})
        resp.raise_for_status()

    # --- Topic operations ---

    def list_topics(self, bot_id: str) -> list:
        filter_q = f"_parentbotid_value eq {bot_id} and componenttype eq 9"
        url = self._url(f"botcomponents?$select=botcomponentid,name,statecode&$filter={filter_q}&$orderby=name")
        resp = requests.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_topic(self, topic_id: str) -> dict:
        resp = requests.get(self._url(f"botcomponents({topic_id})"), headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def create_topic(self, bot_id: str, name: str, content: str) -> dict:
        payload = {
            "name": name,
            "componenttype": 9,
            "content": content,
            "_parentbotid_value": bot_id,
        }
        resp = requests.post(self._url("botcomponents"), headers=self._headers(), json=payload)
        resp.raise_for_status()
        return {"id": self._extract_id(resp), "name": name}

    def update_topic(self, topic_id: str, content: str) -> None:
        resp = requests.patch(
            self._url(f"botcomponents({topic_id})"),
            headers=self._headers(),
            json={"content": content},
        )
        resp.raise_for_status()


# --- CLI command handlers ---

def cmd_list_agents(client: CopilotStudioClient, args):
    agents = client.list_agents()
    if not agents:
        print("No agents found.")
        return
    for a in agents:
        status = "active" if a.get("statecode") == 0 else "inactive"
        print(f"{a['name']}  [{status}]")
        print(f"  id:     {a['botid']}")
        print(f"  schema: {a.get('schemaname', 'N/A')}")
        print()


def cmd_get_agent(client: CopilotStudioClient, args):
    print(json.dumps(client.get_agent(args.bot_id), indent=2))


def cmd_create_agent(client: CopilotStudioClient, args):
    schema = args.schema_name or args.name.lower().replace(" ", "_")
    result = client.create_agent(args.name, schema, args.language, args.description or "")
    print(f"Created: {result['name']}")
    print(f"  id: {result['id']}")


def cmd_update_agent(client: CopilotStudioClient, args):
    updates = json.loads(args.json)
    client.update_agent(args.bot_id, updates)
    print(f"Updated agent {args.bot_id}")


def cmd_list_topics(client: CopilotStudioClient, args):
    topics = client.list_topics(args.bot_id)
    if not topics:
        print("No topics found.")
        return
    for t in topics:
        status = "active" if t.get("statecode") == 0 else "inactive"
        print(f"{t['name']}  [{status}]")
        print(f"  id: {t['botcomponentid']}")
        print()


def cmd_get_topic(client: CopilotStudioClient, args):
    topic = client.get_topic(args.topic_id)
    if args.content_only:
        print(topic.get("content", ""))
    else:
        print(json.dumps(topic, indent=2))


def _read_content(content_file: str | None) -> str:
    if content_file:
        with open(content_file) as f:
            return f.read()
    print("Paste topic YAML content, then press Ctrl+D:")
    return sys.stdin.read()


def cmd_create_topic(client: CopilotStudioClient, args):
    content = _read_content(args.content_file)
    result = client.create_topic(args.bot_id, args.name, content)
    print(f"Created topic: {result['name']}")
    print(f"  id: {result['id']}")


def cmd_update_topic(client: CopilotStudioClient, args):
    content = _read_content(args.content_file)
    client.update_topic(args.topic_id, content)
    print(f"Updated topic {args.topic_id}")


def cmd_publish(client: CopilotStudioClient, args):
    client.publish_agent(args.bot_id)
    print(f"Published agent {args.bot_id}")


# --- Argument parser ---

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copilot Studio CLI — manage agents and topics via the Power Platform API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Required env vars:
  COPILOT_STUDIO_TENANT_ID       Azure AD tenant ID
  COPILOT_STUDIO_CLIENT_ID       App registration client ID
  COPILOT_STUDIO_CLIENT_SECRET   App registration client secret
  COPILOT_STUDIO_ENVIRONMENT_URL Dataverse URL (https://yourorg.crm.dynamics.com)
""",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    sub.add_parser("list-agents", help="List all agents in the environment")

    p = sub.add_parser("get-agent", help="Get full details of an agent")
    p.add_argument("bot_id", metavar="BOT_ID")

    p = sub.add_parser("create-agent", help="Create a new agent")
    p.add_argument("name", help="Display name")
    p.add_argument("--schema-name", help="Unique schema name (default: derived from name)")
    p.add_argument("--language", default="en-US", help="Language code (default: en-US)")
    p.add_argument("--description", help="Agent description")

    p = sub.add_parser("update-agent", help="Update agent fields (JSON patch)")
    p.add_argument("bot_id", metavar="BOT_ID")
    p.add_argument("--json", required=True, metavar="JSON", help='JSON object, e.g. \'{"name":"New Name"}\'')

    p = sub.add_parser("list-topics", help="List topics for an agent")
    p.add_argument("bot_id", metavar="BOT_ID")

    p = sub.add_parser("get-topic", help="Get full details of a topic")
    p.add_argument("topic_id", metavar="TOPIC_ID")
    p.add_argument("--content-only", action="store_true", help="Print only the YAML content field")

    p = sub.add_parser("create-topic", help="Create a topic for an agent")
    p.add_argument("bot_id", metavar="BOT_ID")
    p.add_argument("name", help="Topic display name")
    p.add_argument("-f", "--content-file", metavar="FILE", help="YAML file with topic content (stdin if omitted)")

    p = sub.add_parser("update-topic", help="Replace topic content")
    p.add_argument("topic_id", metavar="TOPIC_ID")
    p.add_argument("-f", "--content-file", metavar="FILE", help="YAML file with new content (stdin if omitted)")

    p = sub.add_parser("publish", help="Publish an agent")
    p.add_argument("bot_id", metavar="BOT_ID")

    return parser


COMMANDS = {
    "list-agents": cmd_list_agents,
    "get-agent": cmd_get_agent,
    "create-agent": cmd_create_agent,
    "update-agent": cmd_update_agent,
    "list-topics": cmd_list_topics,
    "get-topic": cmd_get_topic,
    "create-topic": cmd_create_topic,
    "update-topic": cmd_update_topic,
    "publish": cmd_publish,
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    client = CopilotStudioClient()
    try:
        COMMANDS[args.command](client, args)
    except requests.HTTPError as e:
        print(f"API error {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
