# 培训模块 API 文档

**Base URL**: `/api/v1`

**鉴权**: 所有接口需在请求头携带 `Authorization: Bearer <token>`

**通用响应格式**:

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

错误时 `code` 非 200，`data` 为 `null`。

---

## 目录

- [课程管理](#课程管理)
  - [1. 创建课程并生成考题](#1-创建课程并生成考题)
  - [2. 获取课程列表](#2-获取课程列表)
  - [3. 删除课程](#3-删除课程)
- [题库管理](#题库管理)
  - [4. 获取题目列表](#4-获取题目列表)
  - [5. 考题生成入口说明](#5-考题生成入口说明)
- [试卷管理](#试卷管理)
  - [6. 生成试卷](#6-生成试卷)
  - [7. 获取试卷详情](#7-获取试卷详情)
- [考试管理](#考试管理)
  - [8. 提交答卷（异步判分）](#8-提交答卷异步判分)
  - [9. 获取考试结果](#9-获取考试结果)
  - [10. 生成考试评价（异步）](#10-生成考试评价异步)
  - [11. 获取考试记录列表](#11-获取考试记录列表)
- [枚举值参考](#枚举值参考)
- [典型对接流程](#典型对接流程)

---

## 课程管理

### 1. 创建课程并生成考题

创建课程后，服务端会在后台异步触发考题生成，无需再单独调用题目生成接口。

**POST** `/spaces/{space_id}/courses/`

**权限**: `training:write`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**请求体** `application/json`

```json
{
  "name": "网络安全基础培训",
  "description": "面向新员工的网络安全知识培训",
  "kbase_id": "kb_security_2026",
  "doc_id": "res-abc-123",
  "question_number": 10
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 课程名称 |
| description | string | 否 | 课程描述 |
| kbase_id | string | 是 | 知识库 ID，内部映射为出题服务的 `collection_name` |
| doc_id | string | 是 | 文档 ID，内部映射为出题服务的 `file_id` |
| question_number | int | 是 | 需要生成的总题数，必须为正整数 |

> **出题拆分规则**: 服务端会按原出题逻辑自动拆分数量，约每 5 题包含 4 道选择题和 1 道简答题，即 `short_answer_count = question_number // 5`，其余题目按选择题生成。

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "3f2a1b4c-...",
    "title": "网络安全基础培训",
    "question_number": 10,
    "choice_count": 8,
    "short_answer_count": 2,
    "message": "课程创建成功，考题生成任务已提交"
  }
}
```

---

### 2. 获取课程列表

**GET** `/spaces/{space_id}/courses/`

**权限**: `training:read`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "uuid": "3f2a1b4c-...",
        "title": "网络安全基础培训",
        "description": "面向新员工的网络安全知识培训",
        "logo": "https://example.com/logo.png",
        "created_at": "2026-03-29 10:00:00"
      }
    ]
  }
}
```

---

### 3. 删除课程

软删除课程（标记为无效，不物理删除）。

**DELETE** `/spaces/{space_id}/courses/{course_id}/`

**权限**: `training:write`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| course_id | string | 课程 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "deleted": true
  }
}
```

---

## 题库管理

### 4. 获取题目列表

分页查询空间下的所有有效题目及选项。

**GET** `/spaces/{space_id}/courses/{course_id}/questions/`

**权限**: `training:read`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| course_id | string | 课程 ID |

**Query 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| size | int | 10 | 每页数量 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 50,
    "page": 1,
    "size": 10,
    "items": [
      {
        "uuid": "a1b2c3d4-...",
        "type": "single_choice",
        "stem": "以下哪项是SQL注入的常见手段？",
        "analysis": "SQL注入通常通过在输入字段中插入恶意SQL代码...",
        "difficulty": 3,
        "default_score": 5,
        "options": [
          { "key": "A", "content": "在URL中添加恶意SQL语句", "is_correct": 1 },
          { "key": "B", "content": "修改CSS样式", "is_correct": 0 },
          { "key": "C", "content": "清除浏览器缓存", "is_correct": 0 },
          { "key": "D", "content": "更新操作系统", "is_correct": 0 }
        ]
      },
      {
        "uuid": "b2c3d4e5-...",
        "type": "short_answer",
        "stem": "简述XSS攻击的原理和防范措施。",
        "analysis": null,
        "difficulty": 4,
        "default_score": 10,
        "options": []
      }
    ]
  }
}
```

---

### 5. 考题生成入口说明

原 `POST /spaces/{space_id}/courses/{course_id}/questions/` 已合并到 [创建课程并生成考题](#1-创建课程并生成考题) 接口，不再单独提供。

> **前端提示**: 创建课程成功仅表示建课完成且出题任务已提交。题目仍是异步入库，请轮询[获取题目列表](#4-获取题目列表)确认题目已生成完成。

---

## 试卷管理

### 6. 生成试卷

从题库中按题型随机抽题组卷，或直接指定题目 ID。题目不足时在 `shortages` 字段返回差额信息。

**POST** `/spaces/{space_id}/courses/{course_id}/paper/`

**权限**: `training:write`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| course_id | string | 课程 ID |

**请求体** `application/json`

**方式一：按题型数量随机抽题**

```json
{
  "title": "2026年第一季度安全考试",
  "description": "考试时长60分钟，满分100分",
  "duration_minutes": 60,
  "single_choice": 10,
  "multiple_choice": 5,
  "true_false": 5,
  "short_answer": 2
}
```

**方式二：指定题目 ID**

```json
{
  "title": "自定义试卷",
  "duration_minutes": 45,
  "question_ids": ["q1-uuid", "q2-uuid", "q3-uuid"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 否 | 试卷标题，默认 `"考试试卷"` |
| description | string | 否 | 试卷描述 |
| duration_minutes | int | 否 | 考试时长（分钟） |
| single_choice | int | 否 | 单选题数量 |
| multiple_choice | int | 否 | 多选题数量 |
| true_false | int | 否 | 判断题数量 |
| short_answer | int | 否 | 简答题数量 |
| question_ids | string[] | 否 | 直接指定题目 UUID 列表（与题型数量参数二选一） |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "paper-uuid-...",
    "title": "2026年第一季度安全考试",
    "description": "考试时长60分钟，满分100分",
    "duration_minutes": 60,
    "total_score": 100,
    "shortages": [
      {
        "type": "multiple_choice",
        "requested": 5,
        "actual": 3,
        "shortage": 2
      }
    ],
    "questions": [
      {
        "uuid": "q1-...",
        "type": "single_choice",
        "stem": "以下哪项是SQL注入的常见手段？",
        "analysis": "...",
        "difficulty": 3,
        "score": 5,
        "options": [
          { "key": "A", "content": "在URL中添加恶意SQL语句", "is_correct": 1 },
          { "key": "B", "content": "修改CSS样式", "is_correct": 0 },
          { "key": "C", "content": "清除浏览器缓存", "is_correct": 0 },
          { "key": "D", "content": "更新操作系统", "is_correct": 0 }
        ]
      },
      {
        "uuid": "q2-...",
        "type": "short_answer",
        "stem": "简述XSS攻击的原理和防范措施。",
        "analysis": null,
        "difficulty": 4,
        "score": 10,
        "options": []
      }
    ]
  }
}
```

> **注意**: `shortages` 为 `null` 表示所有题型数量均满足需求。前端应检查此字段并提示用户。

> **前端提示**: 考试进行中不应向考生展示 `is_correct` 和 `analysis` 字段，请在前端过滤。

---

### 7. 获取试卷详情

获取试卷完整内容，包含所有题目和选项。

**GET** `/spaces/{space_id}/courses/{course_id}/paper/{paper_id}`

**权限**: `training:read`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| course_id | string | 课程 ID |
| paper_id | string | 试卷 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "paper-uuid-...",
    "title": "2026年第一季度安全考试",
    "description": "考试时长60分钟，满分100分",
    "duration_minutes": 60,
    "total_score": 100,
    "questions": [
      {
        "uuid": "q1-...",
        "type": "single_choice",
        "stem": "题目内容...",
        "analysis": "解析内容...",
        "difficulty": 3,
        "score": 5,
        "options": [
          { "key": "A", "content": "选项A", "is_correct": 1 },
          { "key": "B", "content": "选项B", "is_correct": 0 }
        ]
      }
    ]
  }
}
```

---

## 考试管理

### 8. 提交答卷（异步）

提交考试答案，立即返回 `exam_session_id`。后台异步完成全部判分：客观题即时自动判分，简答题调用 AI 服务评分。

**POST** `/spaces/{space_id}/courses/{course_id}/results/`

**权限**: `training:write`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| course_id | string | 课程 ID |

**请求体** `application/json`

```json
{
  "paper_id": "paper-uuid-...",
  "user_id": "user-uuid-...",
  "answers": [
    {
      "question_id": "q1-uuid",
      "answer": "A"
    },
    {
      "question_id": "q2-uuid",
      "answer": "A,C,D"
    },
    {
      "question_id": "q3-uuid",
      "answer": "A"
    },
    {
      "question_id": "q4-uuid",
      "answer": "XSS攻击是指攻击者在网页中注入恶意脚本代码..."
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| paper_id | string(UUID) | 是 | 试卷 ID |
| user_id | string(UUID) | 是 | 考生用户 ID |
| answers | array | 是 | 答案列表 |
| answers[].question_id | string(UUID) | 是 | 题目 ID |
| answers[].answer | string | 是 | 作答内容（格式见下表） |

**answer 字段格式约定**

| 题型 | 格式 | 示例 |
|------|------|------|
| single_choice | 单个选项字母 | `"A"` |
| multiple_choice | 逗号分隔的选项字母 | `"A,C,D"` |
| true_false | 正确选项字母 | `"A"` |
| short_answer | 自由文本 | `"XSS攻击是指..."` |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "exam_session_id": "es-uuid-..."
  }
}
```

> **前端提示**: 返回后需轮询[获取考试结果](#9-获取考试结果)接口，当 `status` 变为 `"graded"` 时表示判分完成。含简答题时因需调用 AI 评分，耗时可能较长。

---

### 9. 获取考试结果

查询某次考试的判分结果，包含每道题的作答详情和得分。

**GET** `/spaces/{space_id}/courses/{course_id}/results/{exam_session_id}`

**权限**: `training:read`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| course_id | string | 课程 ID |
| exam_session_id | string | 考试会话 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "es-uuid-...",
    "paper_id": "paper-uuid-...",
    "user_id": "user-uuid-...",
    "status": "graded",
    "objective_score": 45,
    "subjective_score": 18,
    "total_score": 63,
    "submit_time": "2026-03-29 14:30:00",
    "evaluation": null,
    "answers": [
      {
        "question_id": "q1-uuid",
        "question_type": "single_choice",
        "answer_text": null,
        "answer_json": { "answer": "A" },
        "is_correct": 1,
        "score": 5,
        "judge_status": "auto_graded"
      },
      {
        "question_id": "q2-uuid",
        "question_type": "multiple_choice",
        "answer_text": null,
        "answer_json": { "answer": "A,C,D" },
        "is_correct": 1,
        "score": 8,
        "judge_status": "auto_graded"
      },
      {
        "question_id": "q4-uuid",
        "question_type": "short_answer",
        "answer_text": "XSS攻击是指攻击者在网页中注入恶意脚本代码...",
        "answer_json": null,
        "is_correct": 1,
        "score": 18,
        "judge_status": "auto_graded"
      }
    ]
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 考试状态，见[枚举值](#考试状态-status) |
| objective_score | int | 客观题（选择/判断）总得分 |
| subjective_score | int | 主观题（简答）总得分 |
| total_score | int | 总得分 = objective_score + subjective_score |
| evaluation | string\|null | AI 综合评价（Markdown），需单独调用[生成评价接口](#10-生成考试评价异步)后才有值 |
| answers[].answer_text | string\|null | 简答题的文本答案 |
| answers[].answer_json | object\|null | 客观题的结构化答案 `{"answer": "A"}` |
| answers[].is_correct | int\|null | 1=正确, 0=错误, null=未判 |
| answers[].score | int | 本题得分 |
| answers[].judge_status | string | 判分状态，见[枚举值](#判分状态-judge_status) |

---

### 10. 生成考试评价（异步）

调用外部 AI 服务对考试生成综合评价，结果为 Markdown 格式，存入考试记录的 `evaluation` 字段。

**POST** `/spaces/{space_id}/courses/{course_id}/results/{exam_session_id}/evaluate`

**权限**: `training:write`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| course_id | string | 课程 ID |
| exam_session_id | string | 考试会话 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "message": "考试评价任务已提交"
  }
}
```

> **前端提示**: 提交后轮询[获取考试结果](#9-获取考试结果)接口，当 `evaluation` 字段不为 `null` 时评价生成完成，内容为 Markdown 文本，可直接渲染。

---

### 11. 获取考试记录列表

分页查询空间下的所有考试记录摘要。

**GET** `/spaces/{space_id}/courses/{course_id}/records/`

**权限**: `training:read`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| course_id | string | 课程 ID |

**Query 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| size | int | 10 | 每页数量 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 42,
    "page": 1,
    "size": 10,
    "items": [
      {
        "uuid": "es-uuid-...",
        "paper_id": "paper-uuid-...",
        "user_id": "user-uuid-...",
        "status": "graded",
        "objective_score": 45,
        "total_score": 63,
        "submit_time": "2026-03-29 14:30:00"
      }
    ]
  }
}
```

---

## 枚举值参考

### 题目类型 (question_type)

| 值 | 说明 |
|----|------|
| `single_choice` | 单选题 |
| `multiple_choice` | 多选题 |
| `true_false` | 判断题 |
| `short_answer` | 简答题 |

### 考试状态 (status)

| 值 | 说明 |
|----|------|
| `submitted` | 已提交，判分中 |
| `graded` | 判分完成 |

### 判分状态 (judge_status)

| 值 | 说明 |
|----|------|
| `auto_graded` | 自动判分完成（客观题系统判分，简答题 AI 判分） |
| `pending` | 待判分（AI 评分服务调用失败时的 fallback 状态） |

---

## 典型对接流程

```
┌─────────────────────────────────────────────────────────────┐
│                        生成题目                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 创建课程并提交出题任务 POST /spaces/{sid}/courses/        │
│       ↓ (异步，轮询题目列表等待入库)                            │
│  2. 生成试卷    POST /spaces/{sid}/courses/{cid}/paper/      │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        考试接口                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  3. 获取试卷    GET  /spaces/{sid}/courses/{cid}/paper/{pid} │
│       ↓                                                     │
│  4. 提交答卷    POST /spaces/{sid}/courses/{cid}/results/    │
│       ↓ 立即返回 exam_session_id                             │
│  5. 轮询结果    GET  .../results/{eid}                       │
│       ↓ 等待 status = "graded"                              │
│  6. 查看成绩                                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        评价分析                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  7. 生成评价    POST .../results/{eid}/evaluate              │
│       ↓ (异步，轮询 evaluation 字段)                         │
│  8. 查看评价    GET  .../results/{eid}                       │
│       ↓ evaluation 字段为 Markdown                           │
│  9. 考试记录    GET  /spaces/{sid}/courses/{cid}/records/    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
