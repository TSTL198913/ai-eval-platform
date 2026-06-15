# AI 评测平台 - 部署配置实施计划

## [x] Task 1: 准备环境变量配置文件
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 复制 .env.prod.example 为 .env.prod
  - 根据目标服务器环境修改配置值
  - 配置敏感信息（数据库密码、API Key）
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3
- **Test Requirements**:
  - programmatic TR-1.1: 验证 .env.prod 文件存在且格式正确
  - programmatic TR-1.2: 验证所有必需环境变量已设置
  - human-judgement TR-1.3: 确认敏感信息未硬编码在代码中
- **Notes**: 敏感信息应通过 Secrets 管理或服务器环境变量注入

## [x] Task 2: 配置 Docker Compose 生产文件
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 创建/更新 docker-compose.prod.yml
  - 配置服务端口映射和网络
  - 设置容器资源限制和健康检查
  - 配置日志驱动和持久化存储
- **Acceptance Criteria Addressed**: AC-1, AC-4
- **Test Requirements**:
  - programmatic TR-2.1: 验证 docker-compose.prod.yml 文件存在且格式正确
  - programmatic TR-2.2: 验证健康检查端点配置正确
  - human-judgement TR-2.3: 确认资源限制配置合理
- **Notes**: 参考 docker-compose.yml 模板进行生产环境配置

## [x] Task 3: 配置数据库连接
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 配置 PostgreSQL 连接参数
  - 设置数据库连接池大小
  - 配置数据库备份策略
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - programmatic TR-3.1: 验证数据库连接字符串格式正确
  - programmatic TR-3.2: 验证数据库服务可连接
  - human-judgement TR-3.3: 确认连接池配置符合预期负载
- **Notes**: 使用 PostgreSQL 生产配置（禁用 SQLite）

## [x] Task 4: 配置消息队列（RabbitMQ）
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 配置 RabbitMQ 连接参数
  - 设置虚拟主机和用户权限
  - 配置队列持久化和消息确认
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - programmatic TR-4.1: 验证 RabbitMQ 连接字符串格式正确
  - programmatic TR-4.2: 验证消息队列服务可连接
  - human-judgement TR-4.3: 确认权限配置符合安全要求
- **Notes**: 使用独立的 RabbitMQ 用户，避免使用默认 guest 用户

## [x] Task 5: 配置缓存（Redis）
- **Priority**: P1
- **Depends On**: Task 1
- **Description**:
  - 配置 Redis 连接参数
  - 设置 Redis 密码认证
  - 配置缓存过期策略
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - programmatic TR-5.1: 验证 Redis 连接字符串格式正确
  - programmatic TR-5.2: 验证 Redis 服务可连接
  - human-judgement TR-5.3: 确认密码认证已启用
- **Notes**: 生产环境必须启用密码认证

## [x] Task 6: 配置 LLM API Key
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 配置 DeepSeek API Key
  - 配置 OpenAI API Key（可选）
  - 设置默认 LLM Provider
- **Acceptance Criteria Addressed**: AC-2, AC-3
- **Test Requirements**:
  - programmatic TR-6.1: 验证至少配置一个 LLM API Key
  - human-judgement TR-6.2: 确认 API Key 未提交到代码仓库
- **Notes**: 通过环境变量注入，禁止硬编码

## [x] Task 7: 配置监控和日志
- **Priority**: P1
- **Depends On**: Task 2
- **Description**:
  - 配置 Prometheus metrics 端点
  - 设置日志级别和输出格式
  - 配置日志轮转策略
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - programmatic TR-7.1: 验证 /metrics 端点可访问
  - human-judgement TR-7.2: 确认日志配置符合运维要求
- **Notes**: 建议配置 ELK 或 Loki 进行日志聚合

## [x] Task 8: 配置安全设置
- **Priority**: P0
- **Depends On**: Task 2
- **Description**:
  - 配置 SSL/TLS 证书
  - 设置 CORS 策略
  - 配置访问控制和限流
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - programmatic TR-8.1: 验证 HTTPS 可正常访问
  - human-judgement TR-8.2: 确认 CORS 策略限制合理
- **Notes**: 生产环境必须启用 HTTPS

## [x] Task 9: 配置部署脚本
- **Priority**: P1
- **Depends On**: Task 2
- **Description**:
  - 更新 deploy-prod.sh 脚本
  - 配置零停机部署策略
  - 设置备份和回滚机制
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - programmatic TR-9.1: 验证部署脚本可执行
  - human-judgement TR-9.2: 确认备份机制完整
- **Notes**: 使用 docker compose up -d 实现零停机更新

## [x] Task 10: 部署前验证检查
- **Priority**: P0
- **Depends On**: All previous tasks
- **Description**:
  - 运行配置验证脚本
  - 检查所有必需服务是否可访问
  - 验证健康检查端点
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-4
- **Test Requirements**:
  - programmatic TR-10.1: 所有配置验证通过
  - programmatic TR-10.2: 所有服务健康检查通过
- **Notes**: 必须在正式部署前完成此任务
