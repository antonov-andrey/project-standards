# Project Standards

`project-standards` — отдельный marketplace repository и installable plugin для переиспользуемых междоменных инженерных стандартов пользователя.

Каждый стандарт представлен независимо вызываемым capability skill. Подробный нормативный контракт хранится ровно у одного skill-владельца; зависимые skills ссылаются на этот контракт и не копируют его.

Проект-потребитель выбирает все применимые capabilities в корневом `AGENTS.md`, в разделе `Required Standards`. Применимость определяется фактическими сущностями, технологиями, границами, семействами артефактов и workflows проекта. Пропуск или переопределение применимого стандарта допускается только по явному требованию пользователя.

`project-standardize` выполняет явное обнаружение workspace и классификацию применимых standards. `project-standard-audit` проверяет выбор, доступность владельцев и отсутствие локальных копий. Protected instruction migrations не изменяются автоматически: для них требуется отдельно утверждённый source-to-target ledger.

Этот repository не владеет generic task workflows или domain-specific agent assets. Они принадлежат соответствующим plugins и только ссылаются на применимые engineering standards.
