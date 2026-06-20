# AI Eval Platform - 浠ｇ爜鏍煎紡瑙勮寖

## 1. 鏍煎紡瑙勮寖璇存槑

### 1.1 涓轰粈涔堥渶瑕佷唬鐮佹牸寮忚鑼冿紵

**闂鑳屾櫙**锛?
- Agent鐢熸垚鐨勪唬鐮佺粡甯稿瓨鍦ㄦ牸寮忛棶棰?
- CI缁忓父鍥犱负鏍煎紡闂澶辫触
- 浠ｇ爜椋庢牸涓嶄竴鑷达紝闅句互缁存姢

**瑙ｅ喅鏂规**锛?
- 缁熶竴浣跨敤Black杩涜浠ｇ爜鏍煎紡鍖?
- 缁熶竴浣跨敤Ruff杩涜浠ｇ爜妫€鏌?
- 缁熶竴浣跨敤isort杩涜瀵煎叆鎺掑簭
- 鍚敤CI闂ㄧ锛屽己鍒舵鏌ユ牸寮?

### 1.2 鏍煎紡宸ュ叿閰嶇疆

#### Black閰嶇疆锛坧yproject.toml锛?
```toml
[tool.black]
line-length = 100
target-version = ['py310']
include = '\.pyi?$'
exclude = '''
/(
    \.git
  | \.venv
  | \.eggs
  | build
  | dist
  | __pycache__
)/
'''
```

#### Ruff閰嶇疆锛坧yproject.toml锛?
```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # Pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by formatter)
    "E402",  # module level import not at top of file
    "B008",  # do not perform function calls in argument defaults
    "C901",  # too complex
    "B017",  # assert blind exception (common in tests)
]
```

#### isort閰嶇疆锛坧yproject.toml锛?
```toml
[tool.isort]
profile = "black"
line_length = 100
skip_gitignore = true
skip = [".venv", "build", "dist"]
```

---

## 2. 浠ｇ爜鏍煎紡鍖栧懡浠?

### 2.1 鏈湴鏍煎紡鍖栧懡浠?

```bash
# 瀹夎渚濊禆
pip install black ruff isort

# 鏍煎紡鍖栨墍鏈塒ython鏂囦欢
black src/ tests/

# 妫€鏌ユ牸寮忥紙涓嶄慨鏀癸級
black --check src/ tests/

# 鑷姩淇瀵煎叆鎺掑簭
isort src/ tests/

# 妫€鏌ュ鍏ユ帓搴?
isort --check src/ tests/

# 杩愯Ruff妫€鏌?
ruff check src/ tests/

# 鑷姩淇Ruff闂
ruff check --fix src/ tests/

# 涓€閿牸寮忓寲锛堟帹鑽愶級
black src/ tests/ && isort src/ tests/ && ruff check --fix src/ tests/
```

### 2.2 棰勬彁浜ら挬瀛愰厤缃?

鍒涘缓 `.pre-commit-config.yaml`锛?

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
        language_version: python3.10

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        name: isort (Python)

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

瀹夎棰勬彁浜ら挬瀛愶細
```bash
pip install pre-commit
pre-commit install
```

---

## 3. CI/CD鏍煎紡闂ㄧ

### 3.1 淇鍚庣殑CI閰嶇疆

鍒涘缓 `.github/workflows/code-quality.yml`锛?

```yaml
name: Code Quality

on:
  push:
    branches: [main, develop, develop_06]
  pull_request:
    branches: [main, develop, develop_06]

jobs:
  lint:
    name: Code Quality Check
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Install linting tools
        run: pip install black ruff isort

      # =====================================================================
      # 寮哄埗鏍煎紡鍖栨鏌?
      # =====================================================================
      - name: Check Black formatting
        run: |
          black --check src/ tests/
        id: black

      - name: Check isort formatting
        run: |
          isort --check src/ tests/
        id: isort

      - name: Run Ruff checks
        run: |
          ruff check src/ tests/
        id: ruff

      # =====================================================================
      # 鑷姩鏍煎紡鍖栵紙鍙€夛級
      # =====================================================================
      - name: Auto-format code
        run: |
          black src/ tests/
          isort src/ tests/
          ruff check --fix src/ tests/

      - name: Create Pull Request with fixes
        if: github.event_name == 'pull_request'
        uses: peter-evans/create-pull-request@v5
        with:
          title: 'style: Auto-format code'
          commit-message: 'style: Auto-format code'
          branch: auto-format
          delete-branch: true
```

### 3.2 鍚敤CI闂ㄧ锛堝叧閿紒锛?

淇敼 `.github/workflows/ci.yml`锛?

```yaml
# 鍘熸潵鐨勯厤缃紙闂ㄧ宸叉敞閲婏級
# - name: Run Ruff (Fast Python Linter)
#   run: |
#     ruff check src/ tests/ --output-format=github || true  # [闂ㄧ宸叉敞閲奭 鏆備笉寮哄埗

# 淇鍚庣殑閰嶇疆锛堝惎鐢ㄩ棬绂侊級
- name: Run Ruff (Fast Python Linter)
  run: |
    ruff check src/ tests/ --output-format=github

# 鍘熸潵鐨勯厤缃紙闂ㄧ宸叉敞閲婏級
# - name: Run Black (Code Formatter Check)
#   run: |
#     black --check src/ tests/ || true  # [闂ㄧ宸叉敞閲奭 鏆備笉寮哄埗

# 淇鍚庣殑閰嶇疆锛堝惎鐢ㄩ棬绂侊級
- name: Run Black (Code Formatter Check)
  run: |
    black --check src/ tests/
```

---

## 4. Agent浠ｇ爜鐢熸垚瑙勮寖

### 4.1 Agent蹇呴』閬靛惊鐨勬牸寮忚鑼?

#### 鍛藉悕瑙勮寖
```python
# 鉁?姝ｇ‘鐨勫懡鍚?
class SecurityEvaluator:
    def __init__(self):
        self.client = None
        self._private_method():
        MAX_RETRIES = 3
        user_input = "test"

# 鉂?閿欒鐨勫懡鍚?
class security_evaluator:  # 绫诲悕浣跨敤 snake_case
class Security_Evaluator:  # 绫诲悕鍖呭惈涓嬪垝绾?
def __init__(Self):  # 浣跨敤 self 鑰屼笉鏄?Self
```

#### 瀵煎叆瑙勮寖
```python
# 鉁?姝ｇ‘鐨勫鍏ラ『搴?
# 1. 鏍囧噯搴?
import os
import sys
from typing import Optional, Dict, List

# 2. 绗笁鏂瑰簱
import pytest
from fastapi import FastAPI

# 3. 鏈湴瀵煎叆
from src.domain.evaluators.base import BaseEvaluator
from src.schemas.evaluation import DomainResponse

# 鉂?閿欒鐨勫鍏ラ『搴?
from src.schemas.evaluation import DomainResponse  # 鏈湴瀵煎叆鍦ㄥ墠
import pytest  # 绗笁鏂瑰簱鍦ㄥ悗
import os  # 鏍囧噯搴撳湪鍚?
```

#### 缂╄繘瑙勮寖
```python
# 鉁?姝ｇ‘鐨勭缉杩涳紙4涓┖鏍硷級
def example_function():
    if True:
        for i in range(10):
            print(i)

# 鉂?閿欒鐨勭缉杩涳紙娣峰悎浣跨敤绌烘牸鍜孴ab锛?
def example_function():
    if True:
        for i in range(10):  # Tab缂╄繘
        	print(i)  # 绌烘牸缂╄繘
```

#### 琛岄暱搴﹁鑼?
```python
# 鉁?姝ｇ‘鐨勮闀垮害锛? 100瀛楃锛?
def long_function_name(param1, param2, param3, param4):
    """This is a properly formatted docstring."""
    return param1 + param2 + param3 + param4

# 鉂?杩囬暱鐨勮锛? 100瀛楃锛?
def long_function_name(param1, param2, param3, param4, param5, param6, param7):
    return param1 + param2 + param3 + param4 + param5 + param6 + param7
```

#### 绌鸿瑙勮寖
```python
# 鉁?姝ｇ‘鐨勭┖琛屼娇鐢?
class MyClass:
    def method_one(self):
        """Method one."""
        pass

    def method_two(self):
        """Method two."""
        pass


def standalone_function():
    """Standalone function."""
    pass

# 鉂?缂哄皯绌鸿
class MyClass:
    def method_one(self):
        pass
    def method_two(self):  # 缂哄皯绌鸿
        pass
```

#### 鏂囨。瀛楃涓茶鑼?
```python
# 鉁?姝ｇ‘鐨勬枃妗ｅ瓧绗︿覆
def calculate_score(value: int) -> float:
    """Calculate score based on value.

    Args:
        value: The input value to calculate score for.

    Returns:
        The calculated score as a float.

    Raises:
        ValueError: If value is negative.
    """
    if value < 0:
        raise ValueError("Value must be non-negative")
    return value * 0.1

# 鉂?缂哄皯鏂囨。瀛楃涓?
def calculate_score(value):
    return value * 0.1
```

#### 绫诲瀷娉ㄨВ瑙勮寖
```python
# 鉁?姝ｇ‘鐨勭被鍨嬫敞瑙?
def process_data(data: List[Dict[str, int]]) -> Optional[str]:
    """Process data and return result."""
    if not data:
        return None
    return str(data[0])

# 鉂?缂哄皯绫诲瀷娉ㄨВ
def process_data(data):
    return str(data[0]) if data else None
```

### 4.2 Agent浠ｇ爜鐢熸垚妫€鏌ユ竻鍗?

鍦ㄧ敓鎴愪唬鐮佸悗锛孉gent蹇呴』锛?

- [ ] **杩愯鏍煎紡鍖?*: `black src/ tests/`
- [ ] **杩愯瀵煎叆鎺掑簭**: `isort src/ tests/`
- [ ] **杩愯浠ｇ爜妫€鏌?*: `ruff check src/ tests/`
- [ ] **妫€鏌ュ懡鍚嶈鑼?*: 绫诲悕銆佸嚱鏁板悕銆佸彉閲忓悕
- [ ] **妫€鏌ュ鍏ラ『搴?*: 鏍囧噯搴撱€佺涓夋柟搴撱€佹湰鍦板簱
- [ ] **妫€鏌ョ缉杩?*: 缁熶竴浣跨敤4涓┖鏍?
- [ ] **妫€鏌ヨ闀垮害**: 涓嶈秴杩?00瀛楃
- [ ] **妫€鏌ョ┖琛屼娇鐢?*: 绗﹀悎PEP 8瑙勮寖
- [ ] **妫€鏌ユ枃妗ｅ瓧绗︿覆**: 鍏叡API蹇呴』鏈夋枃妗ｅ瓧绗︿覆
- [ ] **妫€鏌ョ被鍨嬫敞瑙?*: 鍑芥暟鍙傛暟鍜岃繑鍥炲€煎繀椤绘湁绫诲瀷娉ㄨВ

---

## 5. 甯歌鏍煎紡闂鍙婁慨澶?

### 5.1 甯歌闂

#### 闂1锛氬鍏ラ『搴忛敊璇?
```python
# 鉂?閿欒
from src.schemas import DomainResponse
import pytest
import os

# 鉁?姝ｇ‘
import os

import pytest

from src.schemas import DomainResponse
```

**淇鍛戒护**: `isort src/ tests/`

#### 闂2锛氳闀垮害瓒呴檺
```python
# 鉂?閿欒锛堣秴杩?00瀛楃锛?
def long_function_name(parameter1, parameter2, parameter3, parameter4, parameter5):
    return parameter1 + parameter2 + parameter3 + parameter4 + parameter5

# 鉁?姝ｇ‘锛堜娇鐢ㄦ嫭鍙锋崲琛岋級
def long_function_name(
    parameter1, parameter2, parameter3, parameter4, parameter5
):
    return parameter1 + parameter2 + parameter3 + parameter4 + parameter5
```

**淇鍛戒护**: `black src/ tests/`

#### 闂3锛氱己灏戠┖琛?
```python
# 鉂?閿欒锛堢被鍐呮柟娉曠己灏戠┖琛岋級
class MyClass:
    def method_one(self):
        pass
    def method_two(self):
        pass

# 鉁?姝ｇ‘锛堟柟娉曢棿鏈夌┖琛岋級
class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        pass
```

**淇鍛戒护**: `black src/ tests/`

#### 闂4锛氬紩鍙蜂娇鐢ㄤ笉涓€鑷?
```python
# 鉂?閿欒锛堟贩鐢ㄥ崟寮曞彿鍜屽弻寮曞彿锛?
text = 'Hello, World!'
message = "Welcome"

# 鉁?姝ｇ‘锛堢粺涓€浣跨敤鍙屽紩鍙凤級
text = "Hello, World!"
message = "Welcome"
```

**淇鍛戒护**: `black src/ tests/`

#### 闂5锛氱己灏戠被鍨嬫敞瑙?
```python
# 鉂?閿欒锛堢己灏戠被鍨嬫敞瑙ｏ級
def calculate_score(value):
    return value * 0.1

# 鉁?姝ｇ‘锛堟坊鍔犵被鍨嬫敞瑙ｏ級
def calculate_score(value: float) -> float:
    return value * 0.1
```

**淇鍛戒护**: 闇€瑕佹墜鍔ㄦ坊鍔犵被鍨嬫敞瑙?

---

## 6. 楠岃瘉鍜屾祴璇?

### 6.1 楠岃瘉鏍煎紡鍖栭厤缃?

```bash
# 妫€鏌lack閰嶇疆
black --version

# 妫€鏌uff閰嶇疆
ruff --version

# 妫€鏌sort閰嶇疆
isort --version

# 楠岃瘉鎵€鏈夊伐鍏?
black --check src/ && isort --check src/ && ruff check src/
```

### 6.2 淇鑴氭湰

鍒涘缓 `scripts/format_code.sh`:

```bash
#!/bin/bash

echo "寮€濮嬩唬鐮佹牸寮忓寲..."

# 1. 瀹夎渚濊禆
pip install black ruff isort -q

# 2. 鏍煎紡鍖栦唬鐮?
echo "杩愯 Black 鏍煎紡鍖?.."
black src/ tests/

# 3. 鎺掑簭瀵煎叆
echo "杩愯 isort 瀵煎叆鎺掑簭..."
isort src/ tests/

# 4. 妫€鏌ヤ唬鐮?
echo "杩愯 Ruff 浠ｇ爜妫€鏌?.."
ruff check --fix src/ tests/

# 5. 楠岃瘉鏍煎紡鍖?
echo "楠岃瘉鏍煎紡鍖栫粨鏋?.."
if black --check src/ tests/ && isort --check src/ tests/ && ruff check src/ tests/; then
    echo "鉁?浠ｇ爜鏍煎紡妫€鏌ラ€氳繃锛?
    exit 0
else
    echo "鉂?浠ｇ爜鏍煎紡妫€鏌ュけ璐ワ紒"
    exit 1
fi
```

杩愯鑴氭湰锛?
```bash
chmod +x scripts/format_code.sh
./scripts/format_code.sh
```

---

## 7. 鎬荤粨

### 7.1 鏍煎紡瑙勮寖瑕佺偣

1. **缁熶竴宸ュ叿**锛欱lack銆丷uff銆乮sort
2. **缁熶竴閰嶇疆**锛歱yproject.toml
3. **鍚敤闂ㄧ**锛欳I涓己鍒舵鏌ユ牸寮?
4. **棰勬彁浜ら挬瀛?*锛氭湰鍦拌嚜鍔ㄦ牸寮忓寲
5. **Agent瑙勮寖**锛氱敓鎴愪唬鐮佸繀椤婚伒寰牸寮忚鑼?

### 7.2 蹇€熶慨澶嶅懡浠?

```bash
# 涓€閿牸寮忓寲鎵€鏈変唬鐮?
black src/ tests/ && isort src/ tests/ && ruff check --fix src/ tests/

# 楠岃瘉鏍煎紡鍖?
black --check src/ tests/ && isort --check src/ tests/ && ruff check src/ tests/
```

### 7.3 涓嬩竴姝ヨ鍔?

1. 鉁?鍒涘缓浠ｇ爜鏍煎紡瑙勮寖锛堟湰鏂囨。锛?
2. 鈴?鍚敤CI鏍煎紡闂ㄧ锛堜慨鏀筩i.yml锛?
3. 鈴?閰嶇疆棰勬彁浜ら挬瀛愶紙.pre-commit-config.yaml锛?
4. 鈴?鍒涘缓鏍煎紡鍖栬剼鏈紙scripts/format_code.sh锛?
5. 鈴?璁粌Agent閬靛惊鏍煎紡瑙勮寖

---

**鏂囨。鍒涘缓鏃堕棿**: 2026-06-20
**鏈€鍚庢洿鏂?*: 2026-06-20
**缁存姢鑰?*: Trae AI Testing Expert
