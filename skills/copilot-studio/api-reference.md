# Copilot Studio API Reference

## Authentication

Obtain a Bearer token using client credentials:

```
POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id={client_id}
&client_secret={client_secret}
&scope=https://{org}.crm.dynamics.com/.default
```

## Base URL

```
https://{org}.crm.dynamics.com/api/data/v9.2/
```

## Required Headers

```
Authorization: Bearer {token}
Content-Type: application/json
OData-MaxVersion: 4.0
OData-Version: 4.0
Accept: application/json
```

---

## Bot Endpoints

### List Bots
```
GET /bots?$select=botid,name,schemaname,statecode&$orderby=name
```

### Get Bot
```
GET /bots({botId})
```

### Create Bot
```
POST /bots
{
  "name": "My Agent",
  "schemaname": "cr123_myagent",
  "language": "en-US",
  "description": "Optional description"
}
```
Response: `201 Created` — new ID in `OData-EntityId` response header.

### Update Bot
```
PATCH /bots({botId})
{
  "name": "Updated Name",
  "description": "New description"
}
```
Response: `204 No Content`

### Publish Bot
```
POST /bots({botId})/Microsoft.Dynamics.CRM.PublishBotContent
{}
```
Response: `200 OK`

---

## Bot Component (Topic) Endpoints

Topics are stored as `botcomponents` with `componenttype = 9`.

### List Topics for a Bot
```
GET /botcomponents
  ?$select=botcomponentid,name,content,statecode
  &$filter=_parentbotid_value eq {botId} and componenttype eq 9
  &$orderby=name
```

### Get Topic
```
GET /botcomponents({topicId})
```

### Create Topic
```
POST /botcomponents
{
  "name": "Topic Display Name",
  "componenttype": 9,
  "content": "kind: AdaptiveDialog\n...",
  "_parentbotid_value": "{botId}"
}
```
Response: `201 Created` — new ID in `OData-EntityId` response header.

### Update Topic Content
```
PATCH /botcomponents({topicId})
{
  "content": "kind: AdaptiveDialog\n..."
}
```
Response: `204 No Content`

---

## Component Types

| componenttype | Description |
|---------------|-------------|
| 0 | Bot root |
| 9 | Dialog / Topic |
| 10 | Trigger |
| 11 | Variable |
| 15 | Entity |
| 16 | Language understanding model |

---

## OData Query Options

| Option | Example | Description |
|--------|---------|-------------|
| `$select` | `$select=name,botid` | Fields to return |
| `$filter` | `$filter=statecode eq 0` | Filter records |
| `$orderby` | `$orderby=name asc` | Sort order |
| `$top` | `$top=50` | Limit results |
| `$count` | `$count=true` | Include total count |

---

## Common HTTP Status Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| 401 | Unauthorized | Token expired or wrong scope |
| 403 | Forbidden | Service principal not added to environment |
| 404 | Not Found | Wrong bot/topic ID or environment URL |
| 409 | Conflict | Schema name already exists in this environment |
| 412 | Precondition Failed | Missing required field in request body |
