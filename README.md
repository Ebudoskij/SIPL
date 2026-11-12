# SIPL Language Toolkit

Повнофункціональний інструментарій для навчальної імперативної мови програмування **SIPL (Simple Imperative Programming Language)**, розроблений у межах курсового проєкту з дисципліни «Теорія програмування».

Проєкт узгоджено з базовими навчальними матеріалами курсу:
- М.С. Нікітченко. *«Теорія програмування»*, 2010/2020.
- О.В. Шишацька, А.В. Криволап, А.В. Шишацький. *«Теорія програмування. Практикум»*, 2024.

---

## Реалізовані модулі проєкту (сума балів: 11.0 / макс. 10.0)

| Код | Модуль | Бали | Статус | Документація / Тести |
| :--- | :--- | :---: | :---: | :--- |
| `CORE-01` | Формальна специфікація SIPL (БНФ/EBNF, граматика Lark, 12 позитивних та 12 негативних прикладів) | **0.5** | Виконано | [`grammar/sipl.lark`](grammar/sipl.lark), [`docs/grammar.md`](docs/grammar.md), [`tests/test_grammar_spec.py`](tests/test_grammar_spec.py) |
| `CORE-02` | Парсер SIPL та типізоване AST із `SourceSpan` і діагностикою синтаксичних помилок | **1.5** | Виконано | [`src/sipl/ast.py`](src/sipl/ast.py), [`src/sipl/parser.py`](src/sipl/parser.py), [`tests/test_parser_ast.py`](tests/test_parser_ast.py) |
| `CORE-03` | Інтерпретатор SIPL із моделлю стану, обробкою помилок та контролем ліміту кроків (`max_steps`) | **2.0** | Виконано | [`src/sipl/interpreter/`](src/sipl/interpreter/), [`tests/test_interpreter.py`](tests/test_interpreter.py) (покриття `97%`) |
| `CORE-04` | Подієва модель виконання та структуроване трасування (`trace`) у програмному, текстовому та JSON-режимах | **1.0** | Виконано | [`src/sipl/interpreter/trace.py`](src/sipl/interpreter/trace.py), [`tests/test_execution_trace.py`](tests/test_execution_trace.py) |
| `CORE-05` | Інтерфейс командного рядка (`parse`, `check`, `run`, `trace`, `sem`, `sem-eval`, прапорець `--json`, стабільні коди виходу) | **1.0** | Виконано | [`src/sipl/cli.py`](src/sipl/cli.py), [`tests/test_cli.py`](tests/test_cli.py) |
| `CORE-06` | Еталонний набір сумісності (Conformance Suite) з 15 переносимих JSON-специфікацій | **1.0** | Виконано | [`examples/conformance/`](examples/conformance/), [`docs/conformance.md`](docs/conformance.md), [`tests/test_conformance_suite.py`](tests/test_conformance_suite.py) |
| `SEM-01` | Автоматична побудова семантичного терма SIPL у композиційній нотації курсу (`course`, `ascii`, `latex`) | **2.0** | Виконано | [`src/sipl/semantics/terms.py`](src/sipl/semantics/terms.py), [`docs/semantics.md`](docs/semantics.md), [`tests/test_semantics_term.py`](tests/test_semantics_term.py) |
| `SEM-02` | Покрокове обчислення семантичного терма на заданому стані з поясненням застосованих правил ($AF_{AS}, AF_{WH}, \dots$) | **2.0** | Виконано | [`src/sipl/semantics/evaluator.py`](src/sipl/semantics/evaluator.py), [`docs/semantics.md`](docs/semantics.md), [`tests/test_semantics_eval.py`](tests/test_semantics_eval.py) |

---

## Архітектура репозиторію

```text
SIPL/
├── grammar/
│   └── sipl.lark                  # Формальна машиночитана граматика SIPL (CORE-01)
├── src/sipl/
│   ├── __init__.py                # Публічний програмний API пакету sipl
│   ├── __main__.py                # Запуск через python -m sipl
│   ├── grammar.py                 # Завантаження граматики та побудова CST
│   ├── ast.py                     # Типізовані вузли AST та SourceSpan (CORE-02)
│   ├── parser.py                  # CST->AST трансформер та SIPLSyntaxError (CORE-02)
│   ├── interpreter/
│   │   ├── state.py               # Модель стану змінних d ∈ D = V ~-> Z (CORE-03)
│   │   ├── errors.py              # SIPLRuntimeError та підкласи помилок (CORE-03)
│   │   ├── evaluator.py           # Інтерпретатор AST з контролем max_steps (CORE-03)
│   │   └── trace.py               # Подієва модель виконання та ExecutionTrace (CORE-04)
│   ├── semantics/
│   │   ├── terms.py               # Побудова композиційних семантичних термів (SEM-01)
│   │   └── evaluator.py           # Покрокове обчислення термів за правилами AF_* (SEM-02)
│   └── cli.py                     # Інтерфейс командного рядка sipl (CORE-05)
├── examples/
│   ├── valid/                     # 12 валідних прикладів програм SIPL
│   ├── invalid/                   # 12 невалідних прикладів синтаксичних помилок
│   └── conformance/               # 15 JSON-специфікацій еталонного набору (CORE-06)
├── tests/                         # Повний набір автоматичних тестів (pytest)
└── docs/
    ├── grammar.md                 # Специфікація БНФ, лексики, пріоритетів та розширень
    ├── semantics.md               # Документація композиційної семантики (SEM-01, SEM-02)
    └── conformance.md             # Специфікація формату Conformance Suite (CORE-06)
```

---

## Підтримуваний синтаксис SIPL та задокументовані розширення

Базова граматика у [`grammar/sipl.lark`](grammar/sipl.lark) повністю реалізує канонічну БНФ мови SIPL:
- **Програма:** `begin <оператор> end`
- **Оператори:** `x := a`, `S1 ; S2`, `if b then S1 else S2`, `while b do S`, `begin S end`, `skip`
- **Арифметичні вирази:** цілі константи (`... -1, 0, 1, 2 ...`), змінні, `a1 + a2`, `a1 - a2`, `a1 * a2`, `(a)`
- **Умови:** `a1 = a2`, `a1 > a2`, `b1 ∨ b2`, `¬b`, `(b)`

### Задокументовані консервативні розширення відносно базового SIPL:
1. **`!`** — префіксне логічне заперечення (ASCII-синонім канонічного `¬`), відображається у $S^1(neg, sem\langle b \rangle)$.
2. **`||`** — інфіксна логічна диз'юнкція (ASCII-синонім канонічного `∨`), відображається у $S^2(or, sem\langle b_1 \rangle, sem\langle b_2 \rangle)$.
3. **`/`** — інфіксне цілочисельне ділення з пріоритетом множення `*` (аналог `div` із практикуму), відображається у $S^2(div, sem\langle a_1 \rangle, sem\langle a_2 \rangle)$.

Детальний опис пріоритетів (рівні 1–9), асоціативності та лексики наведено у [`docs/grammar.md`](docs/grammar.md).

---

## Встановлення та запуск тестів

### 1. Встановлення пакету в режимі розробки
```bash
python -m venv .venv
# Windows:
.venv\Scripts\pip install -e ".[dev]"
# Linux / macOS / MSYS2:
.venv/bin/pip install -e ".[dev]"
```

### 2. Запуск усіх автоматичних тестів та перевірка покриття
```bash
pytest -v --cov=sipl --cov-report=term-missing
```

### 3. Запуск еталонного набору сумісності (`CORE-06`)
```bash
pytest tests/test_conformance_suite.py -v
```

---

## Приклади використання CLI (`sipl`)

### 1. Перевірка синтаксису (`check`)
```bash
sipl check examples/valid/03_factorial.sipl
sipl check examples/invalid/03_if_without_else.sipl --json
```

### 2. Побудова типізованого дерева AST (`parse`)
```bash
sipl parse examples/valid/03_factorial.sipl
sipl parse examples/valid/03_factorial.sipl --json
```

### 3. Виконання програми на початковому стані (`run`)
```bash
sipl run examples/valid/03_factorial.sipl -s M=5
sipl run examples/valid/04_gcd_euclid_canonical.sipl -s M=48 N=18 --json
```

### 4. Трасування подій виконання (`trace`)
```bash
sipl trace examples/valid/03_factorial.sipl -s M=3
sipl trace examples/valid/03_factorial.sipl -s M=3 --json
```

### 5. Побудова композиційного семантичного терма (`sem` — `SEM-01`)
```bash
# Канонічна нотація курсу:
sipl sem examples/valid/03_factorial.sipl --derivation

# Нотація LaTeX або ASCII:
sipl sem examples/valid/04_gcd_euclid_canonical.sipl --style latex
sipl sem examples/valid/06_primality_check_extensions.sipl --style ascii
```

### 6. Покрокове обчислення семантичного терма на стані (`sem-eval` — `SEM-02`)
```bash
sipl sem-eval examples/valid/03_factorial.sipl -s M=3
sipl sem-eval examples/valid/04_gcd_euclid_canonical.sipl -s M=28 N=12 --json
```

### Коди завершення процесу CLI (`exit codes`)
- `0` — успішне виконання команди;
- `2` — помилка параметрів командного рядка або файл не знайдено;
- `3` — синтаксична помилка у програмі SIPL (`SIPLSyntaxError`);
- `4` — помилка часу виконання (`UninitializedVariableError`, `DivisionByZeroError`, `StepLimitExceededError`).
