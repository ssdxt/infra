## 目录

- [对接说明](#对接说明)
- [1. 获取记忆列表](#1-获取记忆列表)
- [2. 获取记忆详情](#2-获取记忆详情)
- [3. 创建反馈记忆](#3-创建反馈记忆)
- [4. 删除记忆](#4-删除记忆)
- [枚举值与字段说明](#枚举值与字段说明)


---

## 1. 获取记忆列表

**GET** `/spaces/{space_id}/memory`

**权限**: `memory:view`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**Query 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码，最小 1 |
| page_size | int | 20 | 每页数量，范围 1~100 |

**请求示例**

```http
GET /api/v1/spaces/9a4a916d-c325-4bd6-9c0c-bba9340a1001/memory?page=1&page_size=20
```

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "uuid": "d4cb9f0f-468c-4df2-a58e-f405c9fa1001",
        "space_id": "9a4a916d-c325-4bd6-9c0c-bba9340a1001",
        "kbase": [
          {
            "uuid": "5fbb1c47-8c6d-4b29-91db-c80b57fc2001",
            "name": "采购制度知识库"
          },
          {
            "uuid": "087de1e8-93c3-4a25-b193-6e4cb7082002",
            "name": "合同模板知识库"
          }
        ],
        "conversation_id": "01966e35-1db2-7d68-82d6-e0e7c09f3001",
        "user_id": "d2b9251b-52e6-4d6e-96ab-30c60dbe2001",
        "feedback": 1,
        "comment": "回答准确，可以作为后续召回样本",
        "created_at": "2026-04-27 10:30:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| items | array | 记忆列表 |
| items[].uuid | string | 记忆 ID |
| items[].space_id | string | 所属空间 ID |
| items[].kbase | array | 关联知识库对象列表 |
| items[].kbase[].uuid | string | 关联知识库 ID |
| items[].kbase[].name | string | 关联知识库名称 |
| items[].conversation_id | string | 所属会话 ID |
| items[].user_id | string | 创建用户 ID |
| items[].created_at | string | 创建时间 |
| total | int | 总记录数 |
| page | int | 当前页码 |
| page_size | int | 每页数量 |

---

## 2. 获取记忆详情

**GET** `/spaces/{space_id}/memory/{memory_id}`

**权限**: `memory:view`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| memory_id | UUID | 记忆 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "d4cb9f0f-468c-4df2-a58e-f405c9fa1001",
    "space_id": "9a4a916d-c325-4bd6-9c0c-bba9340a1001",
    "kbase": [
      {
        "uuid": "5fbb1c47-8c6d-4b29-91db-c80b57fc2001",
        "name": "采购制度知识库"
      },
      {
        "uuid": "087de1e8-93c3-4a25-b193-6e4cb7082002",
        "name": "合同模板知识库"
      }
    ],
    "conversation_id": "01966e35-1db2-7d68-82d6-e0e7c09f3001",
    "user_id": "d2b9251b-52e6-4d6e-96ab-30c60dbe2001",
    "messages": [
      {
        "uuid": "01966e35-1420-70aa-8f77-6fb9e7a84001",
        "role": "user",
        "content": "给我总结一下知识库里的采购制度",
        "text": "给我总结一下知识库里的采购制度",
        "preview": "给我总结一下知识库里的采购制度",
        "timestamp": 1777237200
      },
      {
        "uuid": "01966e35-18d8-7384-8d8a-74177057d002",
        "role": "agent",
        "content": "采购制度主要包含采购申请、审批、比价和归档四个阶段。",
        "text": "采购制度主要包含采购申请、审批、比价和归档四个阶段。",
        "preview": "采购制度主要包含采购申请、审批、比价和归档四个阶段。",
        "timestamp": 1777237215
      }
    ],
    "feedback": 1,
    "comment": "回答准确，可以作为后续召回样本",
    "created_at": "2026-04-27 10:30:00",
    "updated_at": "2026-04-27 10:30:00"
  }
}
```
---

## 3. 创建反馈记忆

**POST** `/spaces/{space_id}/conversations/{conversation_id}/memory`

**权限**: `memory:write`

**说明**: 该接口用于把一条会话消息及其向前回溯的上下文整理为一条反馈记忆。当前仅写入数据库，向量化存储逻辑仍为待补充状态。

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| conversation_id | UUID | 会话 ID |

**请求体** `application/json`

```json
{
  "message_id": "01966e35-18d8-7384-8d8a-74177057d002",
  "feedback": -1,
  "comment": "这次回答没有结合最新制度版本"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message_id | UUID | 是 | 作为反馈锚点的消息 ID |
| feedback | int | 是 | 反馈值，建议仅传 `-1` 或 `1` |
| comment | string | 否 | 用户评论 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "0f4270e9-9458-4769-92b8-1b267c741003",
    "space_id": "9a4a916d-c325-4bd6-9c0c-bba9340a1001",
    "kbase_id": [
      "5fbb1c47-8c6d-4b29-91db-c80b57fc2001",
      "087de1e8-93c3-4a25-b193-6e4cb7082002"
    ],
    "conversation_id": "01966e35-1db2-7d68-82d6-e0e7c09f3001",
    "user_id": "d2b9251b-52e6-4d6e-96ab-30c60dbe2001",
    "messages": [
      {
        "uuid": "01966e35-1420-70aa-8f77-6fb9e7a84001",
        "role": "user",
        "content": "给我总结一下知识库里的采购制度",
        "text": "给我总结一下知识库里的采购制度",
        "preview": "给我总结一下知识库里的采购制度",
        "timestamp": 1777237200
      },
      {
        "uuid": "01966e35-18d8-7384-8d8a-74177057d002",
        "role": "agent",
        "content": "采购制度主要包含采购申请、审批、比价和归档四个阶段。",
        "text": "采购制度主要包含采购申请、审批、比价和归档四个阶段。",
        "preview": "采购制度主要包含采购申请、审批、比价和归档四个阶段。",
        "timestamp": 1777237215
      }
    ],
    "feedback": -1,
    "comment": "这次回答没有结合最新制度版本",
    "created_at": "2026-04-27 10:35:00",
    "updated_at": "2026-04-27 10:35:00"
  }
}
```

**补充说明**

1. `messages` 并不是前端直接传入，而是服务端根据 `message_id` 从当前会话中回溯整理得到。
2. 当前回溯逻辑按“用户消息 + 助手消息”轮次提取上下文，最多提取受系统配置 `settings.memory.limit` 控制的若干轮消息。

---

## 4. 删除记忆

**DELETE** `/spaces/{space_id}/memory/{memory_id}`

**权限**: `memory:write`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| memory_id | UUID | 记忆 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

---

## 枚举值与字段说明

### feedback

| 值 | 含义 | 说明 |
|----|------|------|
| -1 | 差评 | 表示本次回答效果较差 |
| 1 | 好评 | 表示本次回答效果较好 |

### messages

`messages` 为消息对象数组，来源于聊天记录表中的历史消息片段。单个对象通常包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| uuid | string | 消息 ID |
| role | string | 消息角色，`user` 或 `agent` |
| content | string | 原始消息内容 |
| text | string/null | 纯文本内容 |
| preview | string/null | 消息预览 |
| timestamp | int | Unix 时间戳 |
