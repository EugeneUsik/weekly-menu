'use strict';

// ── State ────────────────────────────────────────────────────────────────────
const state = {
  currentWeekId: null,
  activeScreen: 'menu',
  recipeFilter: 'all',
  expandedRecipeId: null,
  data: {
    index: null,
    recipes: null,
    menu: null,
  },
};

// ── LocalStorage helpers ─────────────────────────────────────────────────────
const LS = {
  getChecked(weekId) {
    try { return new Set(JSON.parse(localStorage.getItem(`wm:checked:${weekId}`)) || []); }
    catch { return new Set(); }
  },
  setChecked(weekId, set) {
    localStorage.setItem(`wm:checked:${weekId}`, JSON.stringify([...set]));
  },
  getFavorites() {
    try { return new Set(JSON.parse(localStorage.getItem('wm:favorites')) || []); }
    catch { return new Set(); }
  },
  setFavorites(set) {
    localStorage.setItem('wm:favorites', JSON.stringify([...set]));
  },
};

// ── Fetch helpers ────────────────────────────────────────────────────────────
async function fetchJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json();
}

// ── Boot sequence ────────────────────────────────────────────────────────────
async function boot() {
  try {
    state.data.index = await fetchJSON('data/index.json');
    state.currentWeekId = state.data.index.defaultWeekId;

    populateWeekSelector(state.data.index.weeks, state.currentWeekId);

    [state.data.recipes, state.data.menu] = await Promise.all([
      fetchJSON('data/recipes.json'),
      fetchJSON(`data/menus/${state.currentWeekId}.json`),
    ]);

    renderActiveScreen();
  } catch (err) {
    showError(err.message);
  }
}

function populateWeekSelector(weeks, currentId) {
  const sel = document.getElementById('week-select');
  sel.innerHTML = weeks
    .filter(w => w.published)
    .map(w => `<option value="${w.weekId}"${w.weekId === currentId ? ' selected' : ''}>${w.labelRu}</option>`)
    .join('');
}

// ── Routing / screen management ──────────────────────────────────────────────
function setActiveScreen(name) {
  state.activeScreen = name;
  document.querySelectorAll('.screen').forEach(el => el.classList.remove('screen--active'));
  document.getElementById(`screen-${name}`).classList.add('screen--active');
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.screen === name);
    btn.setAttribute('aria-selected', btn.dataset.screen === name ? 'true' : 'false');
  });
}

function renderActiveScreen() {
  switch (state.activeScreen) {
    case 'menu':     renderMenu();     break;
    case 'shopping': renderShopping(); break;
    case 'recipes':  renderRecipes();  break;
  }
}

// ── Recipe lookup ────────────────────────────────────────────────────────────
function getRecipe(id) {
  return (state.data.recipes || []).find(r => r.id === id) || null;
}

// ── Menu screen ──────────────────────────────────────────────────────────────
const MEAL_TYPES = ['breakfast', 'lunch', 'dinner', 'snack'];
const MEAL_LABELS = { breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус' };

function renderMenu() {
  const container = document.getElementById('menu-content');
  const menu = state.data.menu;
  if (!menu) { container.innerHTML = '<div class="loading">Загрузка...</div>'; return; }

  const headerCells = ['', ...MEAL_TYPES.map(t => MEAL_LABELS[t])]
    .map(label => `<div>${label}</div>`)
    .join('');

  const rows = menu.days.map(day => {
    const dayLabel = `<div class="menu-day-label">${shortDay(day.dayNameRu)}<br><span style="font-weight:400;color:#999;font-size:11px">${shortDate(day.date)}</span></div>`;
    const cells = MEAL_TYPES.map(type => {
      const meal = day.meals[type];
      if (!meal) return `<div class="menu-cell menu-cell--empty">—</div>`;
      const recipe = getRecipe(meal.recipeId);
      const name = recipe ? recipe.nameRu : meal.recipeId;
      const leftoverClass = meal.isLeftover ? ' menu-cell--leftover' : '';
      return `<div class="menu-cell${leftoverClass}" role="button" tabindex="0" data-recipe-id="${meal.recipeId}" aria-label="${name}">
        <span class="menu-cell-name">${name}</span>
      </div>`;
    }).join('');
    return `<div class="menu-row">${dayLabel}${cells}</div>`;
  }).join('');

  container.innerHTML = `
    <div class="menu-grid">
      <div class="menu-grid-header">${headerCells}</div>
      ${rows}
    </div>`;

  container.querySelectorAll('.menu-cell[data-recipe-id]').forEach(el => {
    el.addEventListener('click', () => openRecipeModal(el.dataset.recipeId));
    el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') openRecipeModal(el.dataset.recipeId); });
  });
}

function shortDay(nameRu) {
  const map = { 'Понедельник':'Пн', 'Вторник':'Вт', 'Среда':'Ср', 'Четверг':'Чт', 'Пятница':'Пт', 'Суббота':'Сб', 'Воскресенье':'Вс' };
  return map[nameRu] || nameRu.slice(0, 2);
}
function shortDate(iso) {
  const [, m, d] = iso.split('-');
  return `${parseInt(d)}.${parseInt(m)}`;
}

// ── Recipe modal (from menu cell) ────────────────────────────────────────────
function openRecipeModal(recipeId) {
  const recipe = getRecipe(recipeId);
  if (!recipe) return;
  const favorites = LS.getFavorites();
  const isFav = favorites.has(recipeId);

  const modal = document.getElementById('recipe-modal');
  const content = document.getElementById('modal-content');

  content.innerHTML = `
    <div class="recipe-card-header">
      <div>
        <div class="recipe-card-title">${recipe.nameRu}</div>
        <div class="recipe-card-meta">${MEAL_LABELS[recipe.mealType]} · ${recipe.activeMinutes} мин активно · ${recipe.totalMinutes} мин всего</div>
      </div>
      <button class="btn-favorite" id="modal-fav" aria-label="Добавить в избранное">${isFav ? '❤️' : '🤍'}</button>
      <button class="btn-close" id="modal-close" aria-label="Закрыть">✕</button>
    </div>
    ${renderRecipeBody(recipe)}`;

  modal.classList.add('modal--open');
  modal.setAttribute('aria-hidden', 'false');

  document.getElementById('modal-close').addEventListener('click', closeRecipeModal);
  document.getElementById('modal-backdrop').addEventListener('click', closeRecipeModal);
  document.getElementById('modal-fav').addEventListener('click', () => {
    const favs = LS.getFavorites();
    if (favs.has(recipeId)) favs.delete(recipeId); else favs.add(recipeId);
    LS.setFavorites(favs);
    document.getElementById('modal-fav').textContent = favs.has(recipeId) ? '❤️' : '🤍';
  });
}

function closeRecipeModal() {
  const modal = document.getElementById('recipe-modal');
  modal.classList.remove('modal--open');
  modal.setAttribute('aria-hidden', 'true');
}

function renderRecipeBody(recipe) {
  const ingredients = recipe.ingredients.map(ing => {
    const map = state.data.menu?.shoppingList?.find(s => s.ingredientId === ing.ingredientId);
    const name = map ? map.nameRu : ing.ingredientId;
    return `<li>${name} — ${ing.amount} ${ing.unit}</li>`;
  }).join('');

  const steps = recipe.stepsRu.map(s => `<li>${s}</li>`).join('');

  const storageHtml = recipe.storageNote
    ? `<div class="recipe-section-label">Хранение</div><p class="recipe-note">${recipe.storageNote}</p>`
    : '';
  const subsHtml = recipe.substitutionsNote
    ? `<div class="recipe-section-label">Замены</div><p class="recipe-note">${recipe.substitutionsNote}</p>`
    : '';

  return `
    <div class="recipe-section-label">Ингредиенты (на ${recipe.servings} порции)</div>
    <ul class="recipe-ingredients">${ingredients}</ul>
    <div class="recipe-section-label">Приготовление</div>
    <ol class="recipe-steps">${steps}</ol>
    ${storageHtml}
    ${subsHtml}`;
}

// ── Shopping screen ──────────────────────────────────────────────────────────
const CATEGORY_LABELS = {
  produce: 'Овощи и фрукты', dairy: 'Молочное', meat: 'Мясо', fish: 'Рыба',
  grains: 'Крупы и злаки', legumes: 'Бобовые', frozen: 'Заморозка',
  pantry: 'Бакалея', other: 'Прочее',
};

function renderShopping() {
  const container = document.getElementById('shopping-content');
  const menu = state.data.menu;
  if (!menu) { container.innerHTML = '<div class="loading">Загрузка...</div>'; return; }

  const checked = LS.getChecked(state.currentWeekId);

  const grouped = {};
  for (const item of menu.shoppingList) {
    if (!grouped[item.category]) grouped[item.category] = [];
    grouped[item.category].push(item);
  }

  const CATEGORY_ORDER = ['produce', 'dairy', 'meat', 'fish', 'legumes', 'grains', 'frozen', 'pantry', 'other'];
  const sortedCategories = CATEGORY_ORDER.filter(c => grouped[c]);

  const html = sortedCategories.map(cat => {
    const items = grouped[cat];
    const rows = items.map(item => {
      const isChecked = checked.has(item.checkboxKey);
      return `<div class="shopping-row${isChecked ? ' shopping-row--checked' : ''}" data-key="${item.checkboxKey}" role="checkbox" aria-checked="${isChecked}" tabindex="0">
        <div class="shopping-checkbox"></div>
        <div class="shopping-name">
          ${item.nameRu}
          ${item.nameLt ? `<div class="shopping-name-lt">${item.nameLt}</div>` : ''}
        </div>
        <div class="shopping-amount">${formatAmount(item.amount, item.unit)}</div>
      </div>`;
    }).join('');

    return `<div class="shopping-category">
      <div class="shopping-category-header">${CATEGORY_LABELS[cat] || cat}</div>
      ${rows}
    </div>`;
  }).join('');

  container.innerHTML = html || '<div class="loading">Список покупок пуст</div>';

  container.querySelectorAll('.shopping-row').forEach(row => {
    const toggle = () => {
      const checked = LS.getChecked(state.currentWeekId);
      const key = row.dataset.key;
      if (checked.has(key)) checked.delete(key); else checked.add(key);
      LS.setChecked(state.currentWeekId, checked);
      renderShopping();
    };
    row.addEventListener('click', toggle);
    row.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') toggle(); });
  });
}

function formatAmount(amount, unit) {
  const n = Number.isInteger(amount) ? amount : amount.toFixed(1).replace(/\.0$/, '');
  const unitLabels = { g: 'г', ml: 'мл', pcs: 'шт', tbsp: 'ст. л.', tsp: 'ч. л.', cup: 'стак.' };
  return `${n} ${unitLabels[unit] || unit}`;
}

// ── Recipes screen ───────────────────────────────────────────────────────────
function renderRecipes() {
  const container = document.getElementById('recipes-content');
  const recipes = state.data.recipes;
  if (!recipes) { container.innerHTML = '<div class="loading">Загрузка...</div>'; return; }

  const favorites = LS.getFavorites();
  let filtered;
  if (state.recipeFilter === 'favorites') {
    filtered = recipes.filter(r => favorites.has(r.id));
  } else if (state.recipeFilter === 'all') {
    filtered = recipes;
  } else {
    filtered = recipes.filter(r => r.mealType === state.recipeFilter);
  }

  if (filtered.length === 0) {
    container.innerHTML = '<div class="loading">Нет рецептов</div>';
    return;
  }

  const html = filtered.map(recipe => {
    const isFav = favorites.has(recipe.id);
    const isExpanded = state.expandedRecipeId === recipe.id;
    return `<div class="recipe-card${isExpanded ? ' recipe-card--expanded' : ''}" data-recipe-id="${recipe.id}">
      <div class="recipe-card-summary">
        <div class="recipe-card-summary-name">${recipe.nameRu}</div>
        <span class="recipe-card-badge">${MEAL_LABELS[recipe.mealType]}</span>
        <button class="recipe-card-fav" data-fav-id="${recipe.id}" aria-label="Избранное">${isFav ? '❤️' : '🤍'}</button>
        <span class="recipe-card-chevron"></span>
      </div>
      <div class="recipe-card-body">
        <div class="recipe-card-meta">${recipe.activeMinutes} мин активно · ${recipe.totalMinutes} мин всего</div>
        ${renderRecipeBody(recipe)}
      </div>
    </div>`;
  }).join('');

  container.innerHTML = `<div class="recipe-list">${html}</div>`;

  container.querySelectorAll('.recipe-card-summary').forEach(summary => {
    summary.addEventListener('click', e => {
      if (e.target.closest('.recipe-card-fav')) return;
      const card = summary.closest('.recipe-card');
      const id = card.dataset.recipeId;
      state.expandedRecipeId = state.expandedRecipeId === id ? null : id;
      renderRecipes();
    });
  });

  container.querySelectorAll('.recipe-card-fav').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const id = btn.dataset.favId;
      const favs = LS.getFavorites();
      if (favs.has(id)) favs.delete(id); else favs.add(id);
      LS.setFavorites(favs);
      renderRecipes();
    });
  });
}

// ── Event wiring ─────────────────────────────────────────────────────────────
document.getElementById('week-select').addEventListener('change', async e => {
  state.currentWeekId = e.target.value;
  try {
    state.data.menu = await fetchJSON(`data/menus/${state.currentWeekId}.json`);
    renderActiveScreen();
  } catch (err) {
    showError(err.message);
  }
});

document.querySelectorAll('.nav-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    setActiveScreen(btn.dataset.screen);
    renderActiveScreen();
  });
});

document.getElementById('btn-check-all').addEventListener('click', () => {
  const menu = state.data.menu;
  if (!menu) return;
  const all = new Set(menu.shoppingList.map(i => i.checkboxKey));
  LS.setChecked(state.currentWeekId, all);
  renderShopping();
});

document.getElementById('btn-reset').addEventListener('click', () => {
  LS.setChecked(state.currentWeekId, new Set());
  renderShopping();
});

document.querySelectorAll('.filter-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    state.recipeFilter = btn.dataset.filter;
    state.expandedRecipeId = null;
    document.querySelectorAll('.filter-tab').forEach(b => b.classList.toggle('active', b === btn));
    renderRecipes();
  });
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeRecipeModal();
});

// ── Error display ────────────────────────────────────────────────────────────
function showError(msg) {
  const existing = document.querySelector('.error-banner');
  if (existing) existing.remove();
  const div = document.createElement('div');
  div.className = 'error-banner';
  div.textContent = `Ошибка: ${msg}`;
  document.querySelector('.main').prepend(div);
}

// ── Start ────────────────────────────────────────────────────────────────────
boot();
