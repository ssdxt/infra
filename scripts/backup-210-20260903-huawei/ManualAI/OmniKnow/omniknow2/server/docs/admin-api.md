# 登录方式
### 接口路由 `/api/v1/auth/login`
### 接口概述
- 请求方式：POST
- 请求类型：JSON

### 请求字段
- **username**: str 用户账户
- **password**: str 用户密码Base64编码

### 响应
- data
    - token：JWT格式Token

- API Endpoint：https://omni-oss.czy3d.com:18365
# 目录

- [对接说明](#对接说明)
- [管理员用户管理](#管理员用户管理)
  - [1. 获取用户列表](#1-获取用户列表)
  - [2. 获取用户详情](#2-获取用户详情)
  - [3. 更新用户状态](#3-更新用户状态)
  - [4. 变更用户角色](#4-变更用户角色)
  - [5. 软删除用户](#5-软删除用户)
- [资源用户组管理](#资源用户组管理)
  - [6. 获取资源用户组列表](#6-获取资源用户组列表)
  - [7. 创建资源用户组](#7-创建资源用户组)
  - [8. 获取资源用户组详情](#8-获取资源用户组详情)
  - [9. 更新资源用户组](#9-更新资源用户组)
  - [10. 删除资源用户组](#10-删除资源用户组)
  - [11. 获取资源组成员列表](#11-获取资源组成员列表)
  - [12. 批量添加资源组成员](#12-批量添加资源组成员)
  - [13. 批量移除资源组成员](#13-批量移除资源组成员)
  - [14. 获取资源组权限列表](#14-获取资源组权限列表)
  - [15. 绑定资源权限到用户组](#15-绑定资源权限到用户组)
  - [16. 解绑资源组权限](#16-解绑资源组权限)
- [ACL 权限总览](#acl-权限总览)
  - [17. 获取空间 ACL 权限列表](#17-获取空间-acl-权限列表)
- [RBAC 角色管理](#rbac-角色管理)
  - [18. 获取角色列表](#18-获取角色列表)
  - [19. 创建角色](#19-创建角色)
  - [20. 获取角色详情](#20-获取角色详情)
  - [21. 更新角色](#21-更新角色)
  - [22. 删除角色](#22-删除角色)
  - [23. 获取角色已绑定权限](#23-获取角色已绑定权限)
  - [24. 批量绑定权限到角色](#24-批量绑定权限到角色)
  - [25. 批量解绑角色权限](#25-批量解绑角色权限)
- [RBAC 权限管理](#rbac-权限管理)
  - [26. 获取权限列表](#26-获取权限列表)
  - [27. 创建权限](#27-创建权限)
  - [28. 获取权限详情](#28-获取权限详情)
  - [29. 更新权限](#29-更新权限)
  - [30. 删除权限](#30-删除权限)
- [用户角色绑定](#用户角色绑定)
  - [31. 获取用户已绑定角色](#31-获取用户已绑定角色)
  - [32. 给用户增量绑定角色](#32-给用户增量绑定角色)
  - [33. 移除用户指定角色](#33-移除用户指定角色)
- [错误码参考](#错误码参考)

---

## 对接说明

1. 所有接口完整前缀均为 `/api/v1/spaces/{space_id}/admin/...`。

---

## 管理员用户管理

### 1. 获取用户列表

**GET** `/spaces/{space_id}/admin/users`

**权限**: `admin:user:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**Query 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码，最小 1 |
| page_size | int | 20 | 每页数量，范围 1~100 |
| keyword | string | - | 按账号或用户名模糊搜索 |
| status | int | - | 用户状态，`1=启用`，`0=禁用` |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 2,
    "page": 1,
    "page_size": 20,
    "users": [
      {
        "space_id": "9a4a916d-c325-4bd6-9c0c-bba9340a1001",
        "space_role": "owner",
        "uuid": "5bce6d08-6b72-4d97-9f06-7f3fcb0cf001",
        "account": "admin",
        "name": "管理员",
        "status": 1,
        "source": "local",
        "roles": ["superadmin"],
        "created_at": "2026-04-14 10:00:00"
      }
    ]
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| space_id | string | 用户所属空间 ID |
| space_role | string | 用户在空间内的角色 |
| uuid | string | 用户 ID |
| account | string | 账号 |
| name | string | 用户名 |
| status | int | 用户状态，`1=启用`，`0=禁用` |
| source | string | 注册来源 |
| roles | string[] | 全局 RBAC 角色编码列表 |
| created_at | string | 创建时间，格式 `YYYY-MM-DD HH:mm:ss` |

---

### 2. 获取用户详情

**GET** `/spaces/{space_id}/admin/users/{user_id}`

**权限**: `admin:user:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| user_id | UUID | 用户 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "5bce6d08-6b72-4d97-9f06-7f3fcb0cf001",
    "account": "admin",
    "name": "管理员",
    "status": 1,
    "source": "local",
    "roles": ["superadmin"],
    "created_at": "2026-04-14 10:00:00",
    "department_name": "技术部",
    "position_name": "系统管理员",
    "tenant_name": "总部"
  }
}
```

**说明**: 详情接口当前返回基础用户信息和 `department_name`、`position_name`、`tenant_name` 等扩展字段；未补充 `space_id`、`space_role`。

---

### 3. 更新用户状态

**PATCH** `/spaces/{space_id}/admin/users/{user_id}/status`

**权限**: `admin:user:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| user_id | UUID | 用户 ID |

**请求体** `application/json`

```json
{
  "status": 0
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | int | 是 | 用户状态，`1=启用`，`0=禁用` |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

---

### 4. 变更用户角色

**PATCH** `/spaces/{space_id}/admin/users/{user_id}/role`

**权限**: `admin:user:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| user_id | UUID | 用户 ID |

**请求体** `application/json`

```json
{
  "role_code": "admin"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| role_code | string | 是 | 角色编码，如 `superadmin`、`admin`、`user` |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

---

### 5. 软删除用户

**DELETE** `/spaces/{space_id}/admin/users/{user_id}`

**权限**: `admin:user:manage`

**说明**: 语义为软删除，服务层逻辑会将用户状态改为禁用。

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| user_id | UUID | 用户 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

---

## 资源用户组管理

### 6. 获取资源用户组列表

**GET** `/spaces/{space_id}/admin/resource-groups`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**Query 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码，最小 1 |
| page_size | int | 20 | 每页数量，范围 1~100 |
| keyword | string | - | 按用户组名称或描述模糊搜索 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 1,
    "page": 1,
    "page_size": 20,
    "groups": [
      {
        "uuid": "9b6fdbaa-e9f9-4f7b-bd7e-11f6c2e98001",
        "name": "知识库管理员组",
        "description": "负责知识库与文档权限维护",
        "status": "active",
        "member_count": 3,
        "created_at": "2026-04-14 10:00:00",
        "updated_at": "2026-04-14 10:00:00"
      }
    ]
  }
}
```

---

### 7. 创建资源用户组

**POST** `/spaces/{space_id}/admin/resource-groups`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**请求体** `application/json`

```json
{
  "name": "知识库管理员组",
  "description": "负责知识库与文档权限维护"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 用户组名称，最大 128 字符 |
| description | string | 否 | 用户组描述，最大 512 字符 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "9b6fdbaa-e9f9-4f7b-bd7e-11f6c2e98001",
    "name": "知识库管理员组",
    "description": "负责知识库与文档权限维护",
    "status": "active"
  }
}
```

---

### 8. 获取资源用户组详情

**GET** `/spaces/{space_id}/admin/resource-groups/{group_id}`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| group_id | UUID | 用户组 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "9b6fdbaa-e9f9-4f7b-bd7e-11f6c2e98001",
    "name": "知识库管理员组",
    "description": "负责知识库与文档权限维护",
    "status": "active",
    "member_count": 3,
    "permissions": [
      {
        "id": 12,
        "resource_type": "knowledge_base",
        "resource_id": "7184fd63-cffe-4f42-bce3-6da72de16001",
        "role": "admin",
        "effect": "allow",
        "created_at": "2026-04-14 10:00:00"
      }
    ],
    "created_at": "2026-04-14 10:00:00",
    "updated_at": "2026-04-14 10:00:00"
  }
}
```

---

### 9. 更新资源用户组

**PUT** `/spaces/{space_id}/admin/resource-groups/{group_id}`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| group_id | UUID | 用户组 ID |

**请求体** `application/json`

```json
{
  "name": "知识库维护组",
  "description": "负责知识库、文档和模型资产权限维护",
  "status": "active"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 用户组名称，最大 128 字符 |
| description | string | 否 | 用户组描述，最大 512 字符 |
| status | string | 否 | 用户组状态，`active` 或 `disabled` |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "9b6fdbaa-e9f9-4f7b-bd7e-11f6c2e98001",
    "name": "知识库维护组",
    "description": "负责知识库、文档和模型资产权限维护",
    "status": "active"
  }
}
```

---

### 10. 删除资源用户组

**DELETE** `/spaces/{space_id}/admin/resource-groups/{group_id}`

**权限**: `admin:acl:manage`

**说明**: 删除时会级联清理用户组成员关系和该组绑定的资源权限记录。

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| group_id | UUID | 用户组 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

---

### 11. 获取资源组成员列表

**GET** `/spaces/{space_id}/admin/resource-groups/{group_id}/members`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| group_id | UUID | 用户组 ID |

**Query 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码，最小 1 |
| page_size | int | 20 | 每页数量，范围 1~100 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 2,
    "page": 1,
    "page_size": 20,
    "members": [
      {
        "user_id": "1da4ff79-6e63-41f2-9040-b87722f08001",
        "user_name": "张三",
        "user_account": "zhangsan",
        "joined_at": "2026-04-14 10:00:00"
      }
    ]
  }
}
```

---

### 12. 批量添加资源组成员

**POST** `/spaces/{space_id}/admin/resource-groups/{group_id}/members`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| group_id | UUID | 用户组 ID |

**请求体** `application/json`

```json
{
  "user_ids": [
    "1da4ff79-6e63-41f2-9040-b87722f08001",
    "240b76e2-c09b-417a-bba1-e3b24b638002"
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_ids | UUID[] | 是 | 批量添加的用户 ID 列表，至少 1 个 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "added": 2
  }
}
```

**说明**: 已在组内的用户会被自动跳过，不会重复报错。

---

### 13. 批量移除资源组成员

**DELETE** `/spaces/{space_id}/admin/resource-groups/{group_id}/members`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| group_id | UUID | 用户组 ID |

**请求体** `application/json`

```json
{
  "user_ids": [
    "1da4ff79-6e63-41f2-9040-b87722f08001"
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_ids | UUID[] | 是 | 批量移除的用户 ID 列表，至少 1 个 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "removed": 1
  }
}
```

---

### 14. 获取资源组权限列表

**GET** `/spaces/{space_id}/admin/resource-groups/{group_id}/permissions`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| group_id | UUID | 用户组 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": 12,
      "resource_type": "knowledge_base",
      "resource_id": "7184fd63-cffe-4f42-bce3-6da72de16001",
      "role": "admin",
      "effect": "allow",
      "created_at": "2026-04-14 10:00:00"
    }
  ]
}
```

---

### 15. 绑定资源权限到用户组

**POST** `/spaces/{space_id}/admin/resource-groups/{group_id}/permissions`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| group_id | UUID | 用户组 ID |

**请求体** `application/json`

```json
{
  "resource_type": "knowledge_base",
  "resource_id": "7184fd63-cffe-4f42-bce3-6da72de16001",
  "role": "admin",
  "effect": "allow"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| resource_type | string | 是 | 资源类型 |
| resource_id | UUID | 是 | 资源 ID |
| role | string | 是 | 授权角色，`owner`、`admin`、`editor`、`viewer` |
| effect | string | 否 | 授权效果，`allow` 或 `deny`，默认 `allow` |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 12,
    "resource_type": "knowledge_base",
    "resource_id": "7184fd63-cffe-4f42-bce3-6da72de16001",
    "role": "admin",
    "effect": "allow"
  }
}
```

---

### 16. 解绑资源组权限

**DELETE** `/spaces/{space_id}/admin/resource-groups/{group_id}/permissions`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| group_id | UUID | 用户组 ID |

**请求体** `application/json`

```json
{
  "resource_type": "knowledge_base",
  "resource_id": "7184fd63-cffe-4f42-bce3-6da72de16001"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| resource_type | string | 是 | 资源类型 |
| resource_id | UUID | 是 | 资源 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

---

## ACL 权限总览

### 17. 获取空间 ACL 权限列表

**GET** `/spaces/{space_id}/admin/permissions`

**权限**: `admin:acl:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": 12,
      "subject_id": "9b6fdbaa-e9f9-4f7b-bd7e-11f6c2e98001",
      "subject_type": "group",
      "resource_type": "knowledge_base",
      "resource_id": "7184fd63-cffe-4f42-bce3-6da72de16001",
      "role": "admin",
      "effect": "allow",
      "created_at": "2026-04-14 10:00:00"
    }
  ]
}
```

**说明**: 该接口返回当前空间下所有处于 `active` 状态的 ACL 记录，不限于资源组详情页视角。

---

## RBAC 角色管理

### 18. 获取角色列表

**GET** `/spaces/{space_id}/admin/rbac/roles`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**Query 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码，最小 1 |
| page_size | int | 20 | 每页数量，范围 1~100 |
| keyword | string | - | 按角色名称或编码模糊搜索 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 3,
    "page": 1,
    "page_size": 20,
    "roles": [
      {
        "uuid": "b64242d7-9263-4e68-8fd8-a0d691d11001",
        "space_id": "9a4a916d-c325-4bd6-9c0c-bba9340a1001",
        "scope": "space",
        "name": "空间审核员",
        "code": "space_auditor",
        "description": "负责空间审核",
        "status": 1,
        "is_builtin": false,
        "created_at": "2026-04-14 10:00:00",
        "updated_at": "2026-04-14 10:00:00"
      }
    ]
  }
}
```

---

### 19. 创建角色

**POST** `/spaces/{space_id}/admin/rbac/roles`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**请求体** `application/json`

```json
{
  "name": "空间审核员",
  "code": "space_auditor",
  "scope": "space",
  "description": "负责空间审核"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 角色名称 |
| code | string | 是 | 角色编码，全局唯一 |
| scope | string | 否 | 作用域，默认 `space` |
| description | string | 否 | 角色描述 |

**响应**: 返回单个角色对象，字段结构同“获取角色列表”中的 `roles[]`。

---

### 20. 获取角色详情

**GET** `/spaces/{space_id}/admin/rbac/roles/{role_id}`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| role_id | UUID | 角色 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "b64242d7-9263-4e68-8fd8-a0d691d11001",
    "space_id": "9a4a916d-c325-4bd6-9c0c-bba9340a1001",
    "scope": "space",
    "name": "空间审核员",
    "code": "space_auditor",
    "description": "负责空间审核",
    "status": 1,
    "is_builtin": false,
    "created_at": "2026-04-14 10:00:00",
    "updated_at": "2026-04-14 10:00:00",
    "permissions": [
      {
        "uuid": "d6d9ca3f-e61d-474a-88aa-2e22f2d02001",
        "space_id": null,
        "name": "角色管理",
        "code": "admin:rbac:manage",
        "description": "管理 RBAC 角色和权限",
        "status": 1,
        "is_builtin": true,
        "created_at": "2026-04-14 10:00:00",
        "updated_at": "2026-04-14 10:00:00"
      }
    ]
  }
}
```

---

### 21. 更新角色

**PUT** `/spaces/{space_id}/admin/rbac/roles/{role_id}`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| role_id | UUID | 角色 ID |

**请求体** `application/json`

```json
{
  "name": "空间审核员-升级版",
  "description": "负责空间审核与复核",
  "status": 1
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 角色名称 |
| description | string | 否 | 角色描述 |
| status | int | 否 | 角色状态，`1=启用`，`0=停用` |

**响应**: 返回更新后的单个角色对象，字段结构同“获取角色列表”中的 `roles[]`。

---

### 22. 删除角色

**DELETE** `/spaces/{space_id}/admin/rbac/roles/{role_id}`

**权限**: `admin:rbac:manage`

**说明**: 当前实现为软删除，将角色 `status` 置为 `0`；系统内置角色不可删除。

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| role_id | UUID | 角色 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

---

### 23. 获取角色已绑定权限

**GET** `/spaces/{space_id}/admin/rbac/roles/{role_id}/permissions`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| role_id | UUID | 角色 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "uuid": "d6d9ca3f-e61d-474a-88aa-2e22f2d02001",
      "space_id": null,
      "name": "角色管理",
      "code": "admin:rbac:manage",
      "description": "管理 RBAC 角色和权限",
      "status": 1,
      "is_builtin": true,
      "created_at": "2026-04-14 10:00:00",
      "updated_at": "2026-04-14 10:00:00"
    }
  ]
}
```

---

### 24. 批量绑定权限到角色

**POST** `/spaces/{space_id}/admin/rbac/roles/{role_id}/permissions`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| role_id | UUID | 角色 ID |

**请求体** `application/json`

```json
{
  "permission_ids": [
    "d6d9ca3f-e61d-474a-88aa-2e22f2d02001",
    "e2c7902e-52f0-4626-b6f4-d50ec52d2002"
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| permission_ids | UUID[] | 是 | 批量绑定的权限 ID 列表，至少 1 个 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "added": 2
  }
}
```

---

### 25. 批量解绑角色权限

**DELETE** `/spaces/{space_id}/admin/rbac/roles/{role_id}/permissions`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| role_id | UUID | 角色 ID |

**请求体** `application/json`

```json
{
  "permission_ids": [
    "d6d9ca3f-e61d-474a-88aa-2e22f2d02001"
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| permission_ids | UUID[] | 是 | 批量解绑的权限 ID 列表，至少 1 个 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "removed": 1
  }
}
```

---

## RBAC 权限管理

### 26. 获取权限列表

**GET** `/spaces/{space_id}/admin/rbac/permissions`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**Query 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码，最小 1 |
| page_size | int | 20 | 每页数量，范围 1~100 |
| keyword | string | - | 按权限名称或编码模糊搜索 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 5,
    "page": 1,
    "page_size": 20,
    "permissions": [
      {
        "uuid": "d6d9ca3f-e61d-474a-88aa-2e22f2d02001",
        "space_id": null,
        "name": "角色管理",
        "code": "admin:rbac:manage",
        "description": "管理 RBAC 角色和权限",
        "status": 1,
        "is_builtin": true,
        "created_at": "2026-04-14 10:00:00",
        "updated_at": "2026-04-14 10:00:00"
      }
    ]
  }
}
```

---

### 27. 创建权限

**POST** `/spaces/{space_id}/admin/rbac/permissions`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |

**请求体** `application/json`

```json
{
  "name": "文档审核",
  "code": "document:audit",
  "description": "审核文档内容"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 权限名称 |
| code | string | 是 | 权限编码，全局唯一 |
| description | string | 否 | 权限描述 |

**响应**: 返回单个权限对象，字段结构同“获取权限列表”中的 `permissions[]`。

---

### 28. 获取权限详情

**GET** `/spaces/{space_id}/admin/rbac/permissions/{permission_id}`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| permission_id | UUID | 权限 ID |

**响应**: 返回单个权限对象，字段结构同“获取权限列表”中的 `permissions[]`。

---

### 29. 更新权限

**PUT** `/spaces/{space_id}/admin/rbac/permissions/{permission_id}`

**权限**: `admin:rbac:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| permission_id | UUID | 权限 ID |

**请求体** `application/json`

```json
{
  "name": "文档审核-增强",
  "description": "审核并复核文档内容",
  "status": 1
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 权限名称 |
| description | string | 否 | 权限描述 |
| status | int | 否 | 权限状态，`1=启用`，`0=停用` |

**响应**: 返回更新后的单个权限对象，字段结构同“获取权限列表”中的 `permissions[]`。

---

### 30. 删除权限

**DELETE** `/spaces/{space_id}/admin/rbac/permissions/{permission_id}`

**权限**: `admin:rbac:manage`

**说明**: 当前实现为软删除，将权限 `status` 置为 `0`；系统内置权限不可删除。

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| permission_id | UUID | 权限 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

---

## 用户角色绑定

### 31. 获取用户已绑定角色

**GET** `/spaces/{space_id}/admin/users/{user_id}/roles`

**权限**: `admin:user:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| user_id | UUID | 用户 ID |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "uuid": "b64242d7-9263-4e68-8fd8-a0d691d11001",
      "space_id": "9a4a916d-c325-4bd6-9c0c-bba9340a1001",
      "scope": "space",
      "name": "空间审核员",
      "code": "space_auditor",
      "description": "负责空间审核",
      "status": 1,
      "is_builtin": false,
      "created_at": "2026-04-14 10:00:00",
      "updated_at": "2026-04-14 10:00:00"
    }
  ]
}
```

---

### 32. 给用户增量绑定角色

**POST** `/spaces/{space_id}/admin/users/{user_id}/roles`

**权限**: `admin:user:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| user_id | UUID | 用户 ID |

**请求体** `application/json`

```json
{
  "role_ids": [
    "b64242d7-9263-4e68-8fd8-a0d691d11001",
    "c9905688-a713-4d7e-aa07-98aa93023002"
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| role_ids | UUID[] | 是 | 批量绑定的角色 ID 列表，至少 1 个 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "added": 2
  }
}
```

---

### 33. 移除用户指定角色

**DELETE** `/spaces/{space_id}/admin/users/{user_id}/roles`

**权限**: `admin:user:manage`

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| space_id | UUID | 空间 ID |
| user_id | UUID | 用户 ID |

**请求体** `application/json`

```json
{
  "role_ids": [
    "b64242d7-9263-4e68-8fd8-a0d691d11001"
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| role_ids | UUID[] | 是 | 批量解绑的角色 ID 列表，至少 1 个 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "removed": 1
  }
}
```

---

## 错误码参考

以下是 admin 模块对接时高频会遇到的错误码：

| 错误码 | 错误信息 | 说明 |
|------|------|------|
| 1010 | 指定用户不存在 | 用户不存在，或用户不属于指定空间 |
| 1110 | 资源用户组不存在 | 资源组不存在或不属于指定空间 |
| 1111 | 同名资源用户组已存在 | 创建或改名时重名 |
| 1113 | 角色不存在 | 角色不存在或当前空间不可见 |
| 1114 | 角色编码已存在 | 创建角色时编码冲突 |
| 1115 | 内置角色不可删除或修改编码 | 删除系统内置角色时触发 |
| 1116 | 权限不存在 | 权限不存在或当前空间不可见 |
| 1117 | 权限编码已存在 | 创建权限时编码冲突 |
| 1118 | 系统内置权限不可删除或修改编码 | 删除系统内置权限时触发 |
| 1013 | 该用户已被禁用，请联系管理员 | 被禁用用户访问接口时可能触发 |
| 1025 | 资源权限不足 | 当前账号没有对应管理权限 |

通用 HTTP 错误：

| HTTP 状态码 | 说明 |
|------|------|
| 401 | Token 无效、缺失或已过期 |
| 403 | RBAC/ACL 权限校验不通过 |
