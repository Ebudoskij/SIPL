# Еталонний набір сумісності SIPL — Conformance Suite (`CORE-06`)

Цей документ описує структуру, формат та спосіб використання еталонного набору сумісності (**Conformance Suite**) для мови програмування **SIPL**, розташованого в директорії [`examples/conformance/`](../examples/conformance/).

Призначення набору:
1. Автоматизована перевірка парсера (`CORE-02`), інтерпретатора (`CORE-03`), CLI (`CORE-05`) та семантичного обчислювача (`SEM-01`, `SEM-02`) на еталонних програмах.
2. Забезпечення **переносимого машиночитаного формату (JSON)**, за яким будь-яка альтернативна реалізація SIPL (на Python чи іншій мові) може перевірити свою відповідність специфікації курсу.

---

## 1. Категорії еталонних тестів

Кожен файл `examples/conformance/*.json` описує один самодостатній тестовий кейс і належить до однієї з трьох категорій (`category`):

1. **`valid_execution`** — синтаксично та семантично коректна програма SIPL, для якої перевіряється:
   - структура дерева абстрактного синтаксису (`expected_ast` або `expected_ast_root_body_type`);
   - композиційний семантичний терм у нотації курсу (`expected_semantic_term`);
   - кінцевий стан змінних (`expected_final_state`) при запуску з початкового стану (`initial_state`);
   - збіг результату між прямим інтерпретатором та обчисленням семантичного терма;
   - код повернення CLI (`expected_exit_code = 0`).
2. **`syntax_error`** — програма з порушенням граматики SIPL, для якої перевіряється:
   - відхилення парсером із типом помилки `SIPLSyntaxError`;
   - підтип синтаксичної помилки (`expected_error_kind`: `UnexpectedToken`, `UnexpectedEOF`, `UnexpectedCharacter`, `EmptySource`);
   - номер рядка виникнення помилки (`expected_line`);
   - код повернення CLI (`expected_exit_code = 3`).
3. **`runtime_error`** — синтаксично коректна програма, яка завершується помилкою виконання (`SIPLRuntimeError`), для якої перевіряється:
   - клас помилки виконання (`expected_error_kind`: `UninitializedVariableError`, `DivisionByZeroError`, `StepLimitExceededError`);
   - код повернення CLI (`expected_exit_code = 4`).

---

## 2. Специфікація JSON-схеми тестового кейсу

```json
{
  "id": "CONF-01",
  "name": "minimal_skip",
  "description": "Людиночитаний опис призначення тесту",
  "category": "valid_execution | syntax_error | runtime_error",
  "source": "begin\n    skip\nend",
  "initial_state": {"X": 42},
  "max_steps": 100,
  "expected_exit_code": 0,
  "expected_semantic_term": "id",
  "expected_final_state": {"X": 42},
  "expected_ast": { "...": "Повне дерево AST із SourceSpan (опційно)" },
  "expected_ast_root_body_type": "SkipStmt | SeqStmt | WhileStmt | IfStmt",
  "expected_error_type": "SIPLSyntaxError | SIPLRuntimeError",
  "expected_error_kind": "UnexpectedToken | UninitializedVariableError | ...",
  "expected_line": 4
}
```

### Опис полів

| Поле | Тип | Обов'язковість | Опис |
| :--- | :--- | :---: | :--- |
| `id` | `string` | Так | Унікальний ідентифікатор тесту (`CONF-01` .. `CONF-15`) |
| `name` | `string` | Так | Коротке символьне ім'я кейсу |
| `description` | `string` | Так | Опис конструкції або правила, що перевіряється |
| `category` | `string` | Так | `valid_execution`, `syntax_error` або `runtime_error` |
| `source` | `string` | Так | Повний вихідний текст програми SIPL |
| `expected_exit_code` | `integer` | Так | Очікуваний код завершення CLI (`0`, `3` або `4`) |
| `initial_state` | `object` | Для `valid_execution`, `runtime_error` | Словник початкових значень змінних (`{"M": 5}`) |
| `max_steps` | `integer` | Опційно (за замовч. `10000`) | Ліміт кроків інтерпретатора |
| `expected_final_state` | `object` | Для `valid_execution` | Очікуваний кінцевий стан змінних після завершення |
| `expected_semantic_term` | `string` | Для `valid_execution` | Очікуваний семантичний терм у канонічній нотації курсу |
| `expected_ast` | `object` | Опційно | Повне очікуване дерево AST у JSON-поданні |
| `expected_ast_root_body_type` | `string` | Опційно | Очікуваний тип кореневого оператора тіла програми |
| `expected_error_type` | `string` | Для `syntax_error`, `runtime_error` | `SIPLSyntaxError` або `SIPLRuntimeError` |
| `expected_error_kind` | `string` | Для `syntax_error`, `runtime_error` | Конкретний підтип помилки |
| `expected_line` | `integer` | Для `syntax_error` | Номер рядка (1-based), де виявлено синтаксичну помилку |

---

## 3. Запуск Conformance Suite

Запуск усього еталонного набору сумісності виконується однією командою:

```bash
pytest tests/test_conformance_suite.py -v
```
