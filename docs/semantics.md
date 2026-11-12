# Композиційна семантика мови SIPL (`SEM-01`, `SEM-02`)

Цей документ описує реалізацію модулів автоматичної побудови композиційних семантичних термів (`SEM-01`, [`src/sipl/semantics/terms.py`](../src/sipl/semantics/terms.py)) та їх покрокового обчислення на станах (`SEM-02`, [`src/sipl/semantics/evaluator.py`](../src/sipl/semantics/evaluator.py)).

---

## 1. Правила побудови семантичного терма (`SEM-01`, Таблиця 1.1 практикуму)

Семантичне відображення $sem$ ставить у відповідність кожній синтаксичній конструкції SIPL терм семантичної алгебри програм $\mathcal{A}_{SIPL}$:

| Код правила | Ім'я правила | Синтаксична конструкція | Семантичний терм ($sem\langle \dots \rangle$) |
| :---: | :--- | :--- | :--- |
| $NP_1$ | `NS_Prog` | `begin S end` | $sem\langle S \rangle$ |
| $NS_1$ | `NS_Stm_As` | `x := a` | $AS^x(sem\langle a \rangle)$ |
| $NS_2$ | `NS_Stm_Seq` | `S1 ; S2` | $sem\langle S_1 \rangle \cdot sem\langle S_2 \rangle$ |
| $NS_3$ | `NS_Stm_If` | `if b then S1 else S2` | $IF(sem\langle b \rangle, sem\langle S_1 \rangle, sem\langle S_2 \rangle)$ |
| $NS_4$ | `NS_Stm_Wh` | `while b do S` | $WH(sem\langle b \rangle, sem\langle S \rangle)$ |
| $NS_5$ | `NS_Stm_Bl` | `begin S end` | $sem\langle S \rangle$ |
| $NS_6$ | `NS_Stm_Sk` | `skip` | $id$ |
| $NA_1$ | `NS_A_Num` | `n` | $\overline{n}$ |
| $NA_2$ | `NS_A_Var` | `x` | $\text{'x}\Rightarrow$ |
| $NA_3$ | `NS_A_Add` | `a1 + a2` | $S^2(add, sem\langle a_1 \rangle, sem\langle a_2 \rangle)$ |
| $NA_4$ | `NS_A_Sub` | `a1 - a2` | $S^2(sub, sem\langle a_1 \rangle, sem\langle a_2 \rangle)$ |
| $NA_5$ | `NS_A_Mult` | `a1 * a2` | $S^2(mult, sem\langle a_1 \rangle, sem\langle a_2 \rangle)$ |
| $NA_{div}$ | `NS_A_Div` | `a1 / a2` *(розширення)* | $S^2(div, sem\langle a_1 \rangle, sem\langle a_2 \rangle)$ |
| $NB_1$ | `NS_B_Eq` | `a1 = a2` | $S^2(eq, sem\langle a_1 \rangle, sem\langle a_2 \rangle)$ |
| $NB_2$ | `NS_B_Gr` | `a1 > a2` | $S^2(gr, sem\langle a_1 \rangle, sem\langle a_2 \rangle)$ |
| $NB_3$ | `NS_B_Or` | `b1 ∨ b2` / `b1 \|\| b2` | $S^2(or, sem\langle b_1 \rangle, sem\langle b_2 \rangle)$ |
| $NB_4$ | `NS_B_Neg` | `¬b` / `!b` | $S^1(neg, sem\langle b \rangle)$ |

---

## 2. Правила обчислення семантичного терма на стані (`SEM-02`, Тема 2 практикуму)

Стан $d \in D = V \stackrel{\sim}{\to} \mathbb{Z}$ подається як скінченна множина іменованих пар $\{x_1 \mapsto v_1, \dots, x_k \mapsto v_k\}$. Модуль `SemanticTermEvaluator` покроково застосовує правила виведення та генерує пояснення кожного переходу:

1. **`AF_CONST` (константна функція):** $\overline{n}(d) = n$.
2. **`AF_DNM` (функція розіменування):** якщо $(x \mapsto v) \in d$, то $\text{'x}\Rightarrow(d) = v$.
3. **`AF_ID` (тотожне перетворення):** $id(d) = d$.
4. **`AF_S` (суперпозиція $S^n$):**
   $$\frac{f_1(d) = v_1, \dots, f_n(d) = v_n, \quad g(v_1, \dots, v_n) = v}{S^n(g, f_1, \dots, f_n)(d) = v}$$
5. **`AF_AS` (композиція присвоювання $AS^x$):**
   $$\frac{f(d) = v}{AS^x(f)(d) = d \nabla \{x \mapsto v\}}$$
6. **`AF_SEQ` (послідовна композиція $\cdot$):**
   $$\frac{f_1(d) = d_1, \quad f_2(d_1) = d_2}{(f_1 \cdot f_2)(d) = d_2}$$
7. **`AF_IF_T` / `AF_IF_F` (композиція розгалуження $IF$):**
   - при $p(d) = T$: $IF(p, f_1, f_2)(d) = f_1(d)$;
   - при $p(d) = F$: $IF(p, f_1, f_2)(d) = f_2(d)$.
8. **`AF_WH_T` / `AF_WH_F` (композиція циклу $WH$):**
   - при $p(d) = F$: $WH(p, f)(d) = d$;
   - при $p(d) = T$: $WH(p, f)(d) = WH(p, f)(f(d))$.
