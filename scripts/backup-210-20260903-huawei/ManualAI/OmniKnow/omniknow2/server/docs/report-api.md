## 目录

- [对接说明](#对接说明)
- [1. 创建报告](#1-创建报告)
- [2. 获取报告列表](#2-获取报告列表)
- [3. 获取报告详情](#3-获取报告详情)
- [4. 更新报告](#4-更新报告)
- [5. 删除报告](#5-删除报告)
- [枚举值参考](#枚举值参考)

---

## 对接说明

1. 报告模块接口统一挂载在空间维度下，完整前缀为 `/api/v1/spaces/{space_id}/reports/`。
2. 列表接口支持 `keyword` 关键词搜索，会对 `title` 和 `content` 做模糊匹配。
3. 列表接口当前仅返回“当前登录用户自己创建的有效报告”，不会返回其他用户创建的报告。
4. 删除为软删除，删除后数据不会物理移除。
5. 更新时间与创建时间格式均为 `YYYY-MM-DD HH:mm:ss`。

---

## 1. 创建报告

**POST** `/spaces/{space_id}/reports/`

**权限**: `report:write`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**请求体** `application/json`

```json
{
  "title": "2026年第15周工作周报",
  "type": "weekly",
  "content": "本周完成了报告搜索接口开发、联调与自测。",
  "extra": {
    "period": "2026-W15",
    "tags": ["研发", "周报"]
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 报告标题 |
| type | string | 是 | 报告类型，见[枚举值参考](#枚举值参考) |
| content | string | 是 | 报告内容 |
| extra | object | 否 | 扩展信息，JSON 对象 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "f98b6f31-2d47-4d84-b7a8-0d9f2d0c1001",
    "title": "2026年第15周工作周报",
    "content": "本周完成了报告搜索接口开发、联调与自测。",
    "type": "weekly",
    "author_id": "d2b9251b-52e6-4d6e-96ab-30c60dbe2001",
    "extra": {
      "period": "2026-W15",
      "tags": ["研发", "周报"]
    },
    "created_at": "2026-04-15 10:30:00",
    "updated_at": "2026-04-15 10:30:00"
  }
}
```

---

## 2. 获取报告列表

支持分页和关键词搜索，关键词会同时匹配 `title`、`content`。

**GET** `/spaces/{space_id}/reports/`

**权限**: `report:read`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**Query 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码，最小 1 |
| page_size | int | 20 | 每页数量，范围 1~100 |
| keyword | string | - | 关键词，按标题和内容模糊搜索 |

**请求示例**

```http
GET /api/v1/spaces/9a4a916d-c325-4bd6-9c0c-bba9340a1001/reports/?page=1&page_size=20&keyword=周报
```

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 2,
    "page": 1,
    "page_size": 20,
    "reports": [
      {
        "uuid": "f98b6f31-2d47-4d84-b7a8-0d9f2d0c1001",
        "title": "2026年第15周工作周报",
        "content": "本周完成了报告搜索接口开发、联调与自测。",
        "type": "weekly",
        "author_id": "d2b9251b-52e6-4d6e-96ab-30c60dbe2001",
        "extra": {
          "period": "2026-W15"
        },
        "created_at": "2026-04-15 10:30:00",
        "updated_at": "2026-04-15 10:30:00"
      },
      {
        "uuid": "0dd36fd7-0d3c-4f73-8f6c-98754f7e1002",
        "title": "产品调研报告",
        "content": "报告中补充了关键词搜索相关说明。",
        "type": "custom",
        "author_id": "d2b9251b-52e6-4d6e-96ab-30c60dbe2001",
        "extra": null,
        "created_at": "2026-04-14 18:00:00",
        "updated_at": "2026-04-14 18:00:00"
      }
    ]
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| total | int | 满足筛选条件的总数 |
| page | int | 当前页码 |
| page_size | int | 每页数量 |
| reports | array | 报告列表 |
| reports[].uuid | string | 报告 ID |
| reports[].title | string | 报告标题 |
| reports[].content | string | 报告内容 |
| reports[].type | string | 报告类型 |
| reports[].author_id | string | 作者用户 ID |
| reports[].extra | object/null | 扩展信息 |
| reports[].created_at | string | 创建时间 |
| reports[].updated_at | string | 更新时间 |

---

## 3. 获取报告详情

**GET** `/spaces/{space_id}/reports/{report_id}/`

**权限**: `report:read`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| report_id | UUID | 报告 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "f98b6f31-2d47-4d84-b7a8-0d9f2d0c1001",
    "title": "2026年第15周工作周报",
    "content": "本周完成了报告搜索接口开发、联调与自测。",
    "type": "weekly",
    "author_id": "d2b9251b-52e6-4d6e-96ab-30c60dbe2001",
    "extra": {
      "period": "2026-W15",
      "tags": ["研发", "周报"]
    },
    "created_at": "2026-04-15 10:30:00",
    "updated_at": "2026-04-15 10:30:00"
  }
}
```

---

## 4. 更新报告

按需传入需要修改的字段，未传字段保持不变。

**PATCH** `/spaces/{space_id}/reports/{report_id}/`

**权限**: `report:write`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| report_id | UUID | 报告 ID |

**请求体** `application/json`

```json
{
  "title": "2026年第15周工作周报（修订版）",
  "content": "本周完成了报告搜索接口开发、联调、自测和文档补充。",
  "extra": {
    "period": "2026-W15",
    "reviewed": true
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 否 | 报告标题 |
| content | string | 否 | 报告内容 |
| extra | object | 否 | 扩展信息 |

> 当前更新接口不支持修改 `type`。

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "f98b6f31-2d47-4d84-b7a8-0d9f2d0c1001",
    "title": "2026年第15周工作周报（修订版）",
    "content": "本周完成了报告搜索接口开发、联调、自测和文档补充。",
    "type": "weekly",
    "author_id": "d2b9251b-52e6-4d6e-96ab-30c60dbe2001",
    "extra": {
      "period": "2026-W15",
      "reviewed": true
    },
    "created_at": "2026-04-15 10:30:00",
    "updated_at": "2026-04-15 11:00:00"
  }
}
```

---

## 5. 删除报告

软删除指定报告。

**DELETE** `/spaces/{space_id}/reports/{report_id}/`

**权限**: `report:write`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| report_id | UUID | 报告 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": true
}
```

---

## 枚举值参考

### `ReportType`

| 值 | 说明 |
|----|------|
| `daily` | 日报 |
| `weekly` | 周报 |
| `monthly` | 月报 |
| `custom` | 自定义报告 |
