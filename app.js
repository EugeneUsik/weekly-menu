'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  currentWeekId:    null,
  activeScreen:     'menu',
  recipeFilter:     'all',
  expandedRecipeId: null,
  data: { index: null, recipes: null, menu: null },
};

// ── LocalStorage ──────────────────────────────────────────────────────────────
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

// ── Fetch ─────────────────────────────────────────────────────────────────────
async function fetchJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Не удалось загрузить ${path} (${res.status})`);
  return res.json();
}

// ── Boot ──────────────────────────────────────────────────────────────────────
async function boot() {
  try {
    state.data.index    = await fetchJSON('data/index.json');
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

// ── Routing ───────────────────────────────────────────────────────────────────
function setActiveScreen(name) {
  state.activeScreen = name;
  document.querySelectorAll('.screen').forEach(el => el.classList.remove('screen--active'));
  document.getElementById(`screen-${name}`).classList.add('screen--active');
  document.querySelectorAll('.nav-tab').forEach(btn => {
    const active = btn.dataset.screen === name;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });
}

function renderActiveScreen() {
  switch (state.activeScreen) {
    case 'menu':     renderMenu();     break;
    case 'shopping': renderShopping(); break;
    case 'recipes':  renderRecipes();  break;
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const MEAL_LABELS = { breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус' };
const MEAL_ICONS  = { breakfast: '☀️',      lunch: '🥗',   dinner: '🍽️',  snack: '🍎' };
const MEAL_TYPES  = ['breakfast', 'lunch', 'dinner', 'snack'];

const MONTHS_SHORT = ['', 'янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const TODAY = todayISO();

function shortDate(iso) {
  const [, m, d] = iso.split('-');
  return `${parseInt(d, 10)} ${MONTHS_SHORT[parseInt(m, 10)]}`;
}

function formatAmount(amount, unit) {
  const n = Number.isInteger(amount) ? amount : parseFloat(amount.toFixed(1));
  const labels = { g: 'г', ml: 'мл', pcs: 'шт', tbsp: 'ст. л.', tsp: 'ч. л.', cup: 'стак.' };
  return `${n}\u202f${labels[unit] || unit}`;
}

function getRecipe(id) {
  return (state.data.recipes || []).find(r => r.id === id) || null;
}

function loadingHTML(text = 'Загрузка...') {
  return `<div class="loading"><div class="loading-spinner"></div><span>${text}</span></div>`;
}

// ── Menu screen ───────────────────────────────────────────────────────────────
function renderMenu() {
  const container = document.getElementById('menu-content');
  const menu      = state.data.menu;
  if (!menu) { container.innerHTML = loadingHTML(); return; }

  const cards = menu.days.map(day => {
    const isToday = day.date === TODAY;

    const mealRows = MEAL_TYPES.map(type => {
      const meal = day.meals[type];
      const icon = MEAL_ICONS[type];

      if (!meal) {
        return `<div class="meal-row meal-row--empty">
          <span class="meal-icon">${icon}</span>
          <span class="meal-name meal-name--empty">—</span>
        </div>`;
      }

      const recipe = getRecipe(meal.recipeId);
      const name   = recipe ? recipe.nameRu : meal.recipeId;

      if (meal.isLeftover) {
        return `<div class="meal-row meal-row--leftover" role="button" tabindex="0" data-recipe-id="${meal.recipeId}" aria-label="${name}">
          <span class="meal-icon">${icon}</span>
          <span class="meal-name">${name}</span>
          <span class="meal-leftover-badge">↩ остаток</span>
        </div>`;
      }

      const time = recipe ? `<span class="meal-time">${recipe.totalMinutes}\u202fмин</span>` : '';
      return `<div class="meal-row" role="button" tabindex="0" data-recipe-id="${meal.recipeId}" aria-label="${name}">
        <span class="meal-icon">${icon}</span>
        <span class="meal-name">${name}</span>
        ${time}
      </div>`;
    }).join('');

    return `<div class="day-card${isToday ? ' day-card--today' : ''}">
      <div class="day-card-header">
        <span class="day-name">${day.dayNameRu}</span>
        <span class="day-date">${shortDate(day.date)}</span>
      </div>
      <div class="day-meals">${mealRows}</div>
    </div>`;
  }).join('');

  container.innerHTML = `<div class="days-list">${cards}</div>`;

  container.querySelectorAll('.meal-row[data-recipe-id]').forEach(el => {
    el.addEventListener('click', () => openRecipeModal(el.dataset.recipeId));
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openRecipeModal(el.dataset.recipeId); }
    });
  });
}

// ── Recipe modal ──────────────────────────────────────────────────────────────
function openRecipeModal(recipeId) {
  const recipe = getRecipe(recipeId);
  if (!recipe) return;

  const isFav = LS.getFavorites().has(recipeId);
  const body  = document.getElementById('modal-body');

  body.innerHTML = `
    <div class="recipe-modal-header">
      <h2 class="recipe-modal-title" id="modal-title">${recipe.nameRu}</h2>
      <button class="btn-favorite" id="modal-fav" aria-label="В избранное">${isFav ? '❤️' : '🤍'}</button>
      <button class="btn-close"    id="modal-close" aria-label="Закрыть">✕</button>
    </div>
    <div class="recipe-modal-meta">
      <span>${MEAL_LABELS[recipe.mealType]}</span>
      <span class="meta-dot"></span>
      <span>${recipe.totalMinutes} мин</span>
      <span class="meta-dot"></span>
      <span>${recipe.servings} порции</span>
    </div>
    ${renderNutritionPills(recipe.nutrition)}
    ${renderRecipeBody(recipe)}`;

  const modal = document.getElementById('recipe-modal');
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

  // Scroll sheet to top whenever opened
  document.getElementById('modal-sheet').scrollTop = 0;
}

function closeRecipeModal() {
  const modal = document.getElementById('recipe-modal');
  modal.classList.remove('modal--open');
  modal.setAttribute('aria-hidden', 'true');
}

function renderNutritionPills(n) {
  if (!n) return '';
  return `<div class="nutrition-strip">
    <span class="nutrition-pill nutrition-pill--kcal">🔥 ${n.kcalPerServing} ккал</span>
    <span class="nutrition-pill nutrition-pill--prot">💪 ${n.proteinG} г белка</span>
    <span class="nutrition-pill nutrition-pill--fat">🧈 ${n.fatG} г жиров</span>
    <span class="nutrition-pill nutrition-pill--carbs">🌾 ${n.carbsG} г углеводов</span>
  </div>`;
}

function renderRecipeBody(recipe) {
  // Build ingredient name map from shopping list (has Russian names)
  const nameMap = {};
  (state.data.menu?.shoppingList || []).forEach(s => { nameMap[s.ingredientId] = s.nameRu; });

  const ingredients = recipe.ingredients.map(ing => {
    const name = nameMap[ing.ingredientId] || ing.ingredientId;
    return `<li><span>${name}</span><span class="ingredient-amount">${formatAmount(ing.amount, ing.unit)}</span></li>`;
  }).join('');

  const steps = recipe.stepsRu.map(s => `<li>${s}</li>`).join('');

  const storageHtml = recipe.storageNote
    ? `<div class="recipe-section-label">Хранение</div><p class="recipe-note">${recipe.storageNote}</p>`
    : '';
  const subsHtml = recipe.substitutionsNote
    ? `<div class="recipe-section-label">Замены</div><p class="recipe-note">${recipe.substitutionsNote}</p>`
    : '';

  return `
    <div class="recipe-section-label">Ингредиенты · ${recipe.servings} порции</div>
    <ul class="recipe-ingredients">${ingredients}</ul>
    <div class="recipe-section-label">Приготовление</div>
    <ol class="recipe-steps">${steps}</ol>
    ${storageHtml}
    ${subsHtml}`;
}

// ── Shopping screen ───────────────────────────────────────────────────────────
const CATEGORY_LABELS = {
  produce: 'Овощи и фрукты', dairy:   'Молочное',  meat:   'Мясо',
  fish:    'Рыба',           grains:  'Крупы',      legumes:'Бобовые',
  frozen:  'Заморозка',      pantry:  'Бакалея',    other:  'Прочее',
};
const CATEGORY_ICONS = {
  produce: '🥦', dairy: '🥛', meat: '🥩', fish:   '🐟',
  grains:  '🌾', legumes: '🫘', frozen: '❄️', pantry: '🧂', other: '📦',
};
const CATEGORY_ORDER = ['produce', 'dairy', 'meat', 'fish', 'legumes', 'grains', 'frozen', 'pantry', 'other'];

function renderShopping() {
  const progressEl  = document.getElementById('shopping-progress');
  const container   = document.getElementById('shopping-content');
  const menu        = state.data.menu;
  if (!menu) { container.innerHTML = loadingHTML(); return; }

  const checked = LS.getChecked(state.currentWeekId);
  const total   = menu.shoppingList.length;
  const done    = menu.shoppingList.filter(i => checked.has(i.checkboxKey)).length;
  const pct     = total ? Math.round(done / total * 100) : 0;

  progressEl.innerHTML = `
    <div class="shopping-progress-row">
      <span>Куплено</span>
      <span class="shopping-progress-count">${done} из ${total}</span>
    </div>
    <div class="shopping-progress-track">
      <div class="shopping-progress-fill" style="width:${pct}%"></div>
    </div>`;

  // Group by category
  const grouped = {};
  for (const item of menu.shoppingList) {
    (grouped[item.category] ??= []).push(item);
  }

  const html = CATEGORY_ORDER
    .filter(cat => grouped[cat])
    .map(cat => {
      const rows = grouped[cat].map(item => {
        const isChecked = checked.has(item.checkboxKey);
        return `<div class="shopping-row${isChecked ? ' shopping-row--checked' : ''}"
                     data-key="${item.checkboxKey}"
                     role="checkbox" aria-checked="${isChecked}" tabindex="0">
          <div class="shopping-checkbox">${isChecked ? '✓' : ''}</div>
          <div class="shopping-name">
            ${item.nameRu}
            ${item.nameLt ? `<div class="shopping-name-lt">${item.nameLt}</div>` : ''}
          </div>
          <div class="shopping-amount">${formatAmount(item.amount, item.unit)}</div>
        </div>`;
      }).join('');

      return `<div class="shopping-category">
        <div class="shopping-category-header">
          <span class="shopping-cat-icon">${CATEGORY_ICONS[cat] || ''}</span>
          ${CATEGORY_LABELS[cat] || cat}
        </div>
        ${rows}
      </div>`;
    }).join('');

  container.innerHTML = html
    ? `<div class="shopping-list">${html}</div>`
    : `<div class="empty-state"><div class="empty-state-icon">🛒</div>Список покупок пуст</div>`;

  container.querySelectorAll('.shopping-row').forEach(row => {
    const toggle = () => {
      const ch  = LS.getChecked(state.currentWeekId);
      const key = row.dataset.key;
      if (ch.has(key)) ch.delete(key); else ch.add(key);
      LS.setChecked(state.currentWeekId, ch);
      renderShopping();
    };
    row.addEventListener('click', toggle);
    row.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
  });
}

// ── Recipes screen ────────────────────────────────────────────────────────────
function renderRecipes() {
  const container = document.getElementById('recipes-content');
  const recipes   = state.data.recipes;
  if (!recipes) { container.innerHTML = loadingHTML(); return; }

  const favorites = LS.getFavorites();

  let filtered;
  if      (state.recipeFilter === 'favorites') filtered = recipes.filter(r => favorites.has(r.id));
  else if (state.recipeFilter === 'all')       filtered = recipes;
  else                                          filtered = recipes.filter(r => r.mealType === state.recipeFilter);

  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">${state.recipeFilter === 'favorites' ? '🤍' : '🍴'}</div>
      ${state.recipeFilter === 'favorites' ? 'Нет избранных рецептов' : 'Нет рецептов'}
    </div>`;
    return;
  }

  const html = filtered.map(recipe => {
    const isFav      = favorites.has(recipe.id);
    const isExpanded = state.expandedRecipeId === recipe.id;
    const icon       = MEAL_ICONS[recipe.mealType] || '🍴';

    return `<div class="recipe-card${isExpanded ? ' recipe-card--expanded' : ''}" data-recipe-id="${recipe.id}">
      <div class="recipe-card-summary">
        <span class="recipe-card-icon">${icon}</span>
        <div class="recipe-card-info">
          <div class="recipe-card-name">${recipe.nameRu}</div>
          <div class="recipe-card-submeta">${recipe.totalMinutes} мин · ${recipe.servings} порции</div>
        </div>
        <button class="recipe-card-fav" data-fav-id="${recipe.id}" aria-label="Избранное">${isFav ? '❤️' : '🤍'}</button>
        <span class="recipe-card-chevron"></span>
      </div>
      <div class="recipe-card-body">
        ${renderNutritionPills(recipe.nutrition)}
        ${renderRecipeBody(recipe)}
      </div>
    </div>`;
  }).join('');

  container.innerHTML = `<div class="recipe-list">${html}</div>`;

  container.querySelectorAll('.recipe-card-summary').forEach(summary => {
    summary.addEventListener('click', e => {
      if (e.target.closest('.recipe-card-fav')) return;
      const card = summary.closest('.recipe-card');
      const id   = card.dataset.recipeId;
      state.expandedRecipeId = state.expandedRecipeId === id ? null : id;
      renderRecipes();
    });
  });

  container.querySelectorAll('.recipe-card-fav').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const id   = btn.dataset.favId;
      const favs = LS.getFavorites();
      if (favs.has(id)) favs.delete(id); else favs.add(id);
      LS.setFavorites(favs);
      renderRecipes();
    });
  });
}

// ── Error display ─────────────────────────────────────────────────────────────
function showError(msg) {
  document.querySelector('.error-banner')?.remove();
  const div = document.createElement('div');
  div.className = 'error-banner';
  div.textContent = `Ошибка: ${msg}`;
  document.querySelector('.main').prepend(div);
}

// ── Event wiring ──────────────────────────────────────────────────────────────
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
  LS.setChecked(state.currentWeekId, new Set(menu.shoppingList.map(i => i.checkboxKey)));
  renderShopping();
});

document.getElementById('btn-reset').addEventListener('click', () => {
  LS.setChecked(state.currentWeekId, new Set());
  renderShopping();
});

document.querySelectorAll('.filter-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    state.recipeFilter     = btn.dataset.filter;
    state.expandedRecipeId = null;
    document.querySelectorAll('.filter-tab').forEach(b => b.classList.toggle('active', b === btn));
    renderRecipes();
  });
});

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeRecipeModal(); });

// ── Start ─────────────────────────────────────────────────────────────────────
boot();
