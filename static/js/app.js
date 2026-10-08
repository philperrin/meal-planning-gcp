/**
   * Meal Planning Assistant - Client-side JS
   * Handles UI transitions, dynamic content rendering, card actions, and server calls.
   */

  // Application State
  let appState = {
    authenticated: (typeof window !== 'undefined' && window.APP_CONFIG && !!window.APP_CONFIG.authenticated) || false,
    db: {
      preferences: {},
      mealPlan: null,
      recipeRatings: {},
      recipeLibrary: {}
    },
    hasApiKey: false,
    apiKeyStatus: {
      hasPersonalKey: false,
      hasSharedKey: false,
      activeKeyType: 'none'
    },
    selectedRecipes: new Set(),
    selectedTags: new Set(),
    lockedIndices: new Set(),
    cuisinePreferences: {},
    pantryIngredients: [],
    reusedRecipes: new Set(),
    historyData: {
      history: [],
      favorites: [],
      ratings: {}
    },
    historyTab: 'recent',
    isOnline: typeof navigator !== 'undefined' ? navigator.onLine !== false : true,
    groceryModeState: {
      active: false,
      selectedCategory: 'all',
      hideChecked: false
    }
  };

  // Master Cuisine List (12 items in alphabetical order)
  const CUISINES = [
    { name: "American / Classic Comfort", icon: "🍔" },
    { name: "Chinese", icon: "🥡" },
    { name: "Indian", icon: "🍛" },
    { name: "Italian", icon: "🍝" },
    { name: "Korean", icon: "🍲" },
    { name: "Mediterranean / Greek", icon: "🫒" },
    { name: "Mexican", icon: "🌮" },
    { name: "Middle Eastern / Levantine", icon: "🧆" },
    { name: "Tex-Mex / Southwestern", icon: "🥑" },
    { name: "Thai", icon: "🍜" },
    { name: "Vegan", icon: "🌱" },
    { name: "Vegetarian", icon: "🥗" }
  ];

  // UI Elements
  const els = {
    tabs: document.querySelectorAll('.nav-tab'),
    views: document.querySelectorAll('.view'),
    loader: document.getElementById('loader'),
    toast: document.getElementById('toast'),

    // Preferences Inputs
    prefAllergies: document.getElementById('pref-allergies'),
    prefDietaryPreferences: document.getElementById('pref-dietary-preferences'),
    prefDiners: document.getElementById('pref-diners'),
    prefMealTime: document.getElementById('pref-meal-time'),
    prefSkipWelcome: document.getElementById('setting-skip-welcome') || document.getElementById('pref-skip-welcome'),
    settingSkipWelcome: document.getElementById('setting-skip-welcome') || document.getElementById('pref-skip-welcome'),
    skipWelcomeCheckbox: document.getElementById('skip-welcome-checkbox'),
    cuisineGrid: document.getElementById('cuisine-grid'),

    // Settings Inputs
    apiKeyInput: document.getElementById('api-key-input'),
    apiBadge: document.getElementById('api-badge'),

    // Planner Inputs
    mealCountInput: document.getElementById('meal-count-input'),
    planPreferencesInput: document.getElementById('plan-preferences-input'),
    pantryTagBox: document.getElementById('pantry-tag-box'),
    pantryPillsContainer: document.getElementById('pantry-pills-container'),
    pantryTagsInput: document.getElementById('pantry-tags-input'),
    btnClearPantry: document.getElementById('btn-clear-pantry'),
    plannerContainer: document.getElementById('planner-container'),
    plannerReuseNotice: document.getElementById('planner-reuse-notice'),

    // History Container & Sub-Navigation
    historyContainer: document.getElementById('history-container'),
    historyDesc: document.getElementById('history-desc'),
    historyReuseBanner: document.getElementById('history-reuse-banner'),
    reuseBannerText: document.getElementById('reuse-banner-text'),
    badgeRecentCount: document.getElementById('badge-recent-count'),
    badgeFavoritesCount: document.getElementById('badge-favorites-count'),
    subtabRecent: document.getElementById('subtab-history-recent'),
    subtabFavorites: document.getElementById('subtab-history-favorites')
  };

  // Initialize App
  document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    setupPantryTagListeners();
    initNetworkListeners();
    initOfflineStorage();
    try {
      if (typeof localStorage !== 'undefined' && localStorage.getItem('meal_planner_skip_welcome') === 'true') {
        switchView('planner');
      }
    } catch (e) { }
    loadInitialData();
    checkUrlParams();
  });

  /**
   * Setup Navigation Event Listeners
   */
  function setupNavigation() {
    document.querySelectorAll('.nav-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const targetView = tab.getAttribute('data-view');
        switchView(targetView);
      });
    });

    // Make brand header title clickable to return to welcome page
    const brandEl = document.querySelector('.brand');
    if (brandEl) {
      brandEl.addEventListener('click', () => switchView('welcome'));
      brandEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          switchView('welcome');
        }
      });
    }

    // Make welcome cards keyboard accessible
    document.querySelectorAll('.welcome-card').forEach(card => {
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          card.click();
        }
      });
    });
  }

  function switchView(viewId) {
    if (!viewId) return;

    if (!appState.authenticated && (viewId === 'history' || viewId === 'preferences' || viewId === 'settings')) {
      viewId = 'planner';
    }

    // Synchronize All Nav Tabs (both desktop header and sticky bottom nav)
    document.querySelectorAll('.nav-tab').forEach(t => {
      if (t.getAttribute('data-view') === viewId) {
        t.classList.add('active');
      } else {
        t.classList.remove('active');
      }
    });

    // Update Main Content Views
    const allViews = document.querySelectorAll('.view');
    allViews.forEach(v => v.classList.remove('active'));
    const targetView = document.getElementById(`${viewId}-view`);
    if (targetView) targetView.classList.add('active');

    // Scroll to top smoothly when switching views
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Fetch history if the tab is selected
    if (viewId === 'history') {
      loadHistoryData();
    }
  }

  /**
   * Load initial data from Drive and User Properties
   */
  function loadInitialData() {
    showLoader("Loading configuration...", "Retrieving your data from Google Drive");
    if (typeof google === 'undefined' || !google.script || !google.script.run) {
      const restored = restorePlanFromOfflineCache();
      hideLoader();
      if (restored) {
        showToast("⚡ Offline Grocery Mode: Restored active plan from local cache.");
      }
      return;
    }
    google.script.run
      .withSuccessHandler(onInitialDataLoaded)
      .withFailureHandler(err => {
        hideLoader();
        const restored = restorePlanFromOfflineCache();
        if (restored) {
          showToast("⚡ Offline Mode: Active meal plan & shopping list loaded from local cache.", false);
        } else {
          showToast("Failed to load initial data: " + err.message, true);
        }
      })
      .loadAppData();
  }

  function onInitialDataLoaded(data) {
    hideLoader();
    if (typeof data.authenticated !== 'undefined') {
      appState.authenticated = !!data.authenticated;
    }
    appState.db = data.db;
    appState.hasApiKey = data.hasApiKey;
    appState.apiKeyStatus = data.apiKeyStatus || {
      hasPersonalKey: data.hasApiKey,
      hasSharedKey: false,
      activeKeyType: data.hasApiKey ? 'personal' : 'none'
    };

    // Populate Preferences Form
    const prefs = appState.db.preferences || {};
    if (els.prefAllergies) els.prefAllergies.value = prefs.allergies || "";
    if (els.prefDietaryPreferences) els.prefDietaryPreferences.value = prefs.dietaryPreferences || "";
    if (els.prefDiners) els.prefDiners.value = prefs.dinersCount || 4;
    if (els.prefMealTime) els.prefMealTime.value = prefs.defaultMealTime || "5:30pm";

    // Ensure Planner Tab inputs are configured
    if (els.planPreferencesInput) {
      els.planPreferencesInput.value = "";
    }
    if (els.mealCountInput && !els.mealCountInput.value) {
      els.mealCountInput.value = 4;
    }

    // Populate and Sync Skip Welcome Checkbox
    const shouldSkip = !!prefs.skipWelcomePage;
    if (els.skipWelcomeCheckbox) els.skipWelcomeCheckbox.checked = shouldSkip;
    if (els.settingSkipWelcome) els.settingSkipWelcome.checked = shouldSkip;
    if (els.prefSkipWelcome) els.prefSkipWelcome.checked = shouldSkip;
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('meal_planner_skip_welcome', shouldSkip ? 'true' : 'false');
      }
    } catch (e) { }

    // If skip preference is enabled and currently on welcome view, switch to planner
    const welcomeView = document.getElementById('welcome-view');
    if (shouldSkip && welcomeView && welcomeView.classList.contains('active')) {
      switchView('planner');
    }

    // Populate Cuisine Preferences
    appState.cuisinePreferences = Object.assign({}, prefs.cuisinePreferences || {});
    renderCuisineGrid();

    // Populate On-Hand Pantry Ingredients (MPA-12)
    const storedPantry = loadPantryIngredientsFromStorage();
    if (appState.db.mealPlan && Array.isArray(appState.db.mealPlan.pantryIngredients) && appState.db.mealPlan.pantryIngredients.length > 0) {
      appState.pantryIngredients = appState.db.mealPlan.pantryIngredients.slice();
    } else if (prefs && Array.isArray(prefs.pantryIngredients) && prefs.pantryIngredients.length > 0) {
      appState.pantryIngredients = prefs.pantryIngredients.slice();
    } else if (storedPantry && storedPantry.length > 0) {
      appState.pantryIngredients = storedPantry;
    } else {
      appState.pantryIngredients = [];
    }
    savePantryIngredientsToStorage();
    renderPantryTags();

    // Restore selected constraint tags and locked indices if present in DB
    if (appState.db.mealPlan) {
      if (Array.isArray(appState.db.mealPlan.selectedTags)) {
        appState.selectedTags = new Set(appState.db.mealPlan.selectedTags);
      }
      if (Array.isArray(appState.db.mealPlan.lockedIndices)) {
        appState.lockedIndices = new Set(appState.db.mealPlan.lockedIndices);
      }
    }
    updateFilterChipsUI();

    // Update API Badge
    updateApiBadge();

    // Render Meal Plan
    renderMealPlan();
  }

  /**
   * Update visual active states for preset constraint chips
   */
  function updateFilterChipsUI() {
    const chips = document.querySelectorAll('.filter-chip');
    chips.forEach(chip => {
      const tag = chip.getAttribute('data-tag');
      if (tag && appState.selectedTags.has(tag)) {
        chip.classList.add('active');
      } else {
        chip.classList.remove('active');
      }
    });
  }

  /**
   * Toggle a preset mood/constraint filter chip
   */
  function handleToggleFilterChip(tagKey) {
    if (!tagKey) return;
    if (appState.selectedTags.has(tagKey)) {
      appState.selectedTags.delete(tagKey);
    } else {
      appState.selectedTags.add(tagKey);
    }
    updateFilterChipsUI();
  }

  /* ==========================================================================
     MPA-12: 'Clean Out the Fridge' / Pantry Priority Tag Functions
     ========================================================================== */

  /**
   * Setup Pantry / Fridge On-Hand Tag Input Listeners
   */
  function setupPantryTagListeners() {
    const input = document.getElementById('pantry-tags-input');
    if (!input) return;

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        const val = input.value;
        if (val && val.trim()) {
          addPantryIngredient(val);
          input.value = '';
        }
      } else if (e.key === 'Backspace' && !input.value && appState.pantryIngredients.length > 0) {
        // Remove last tag on backspace when input is empty
        removePantryIngredient(appState.pantryIngredients.length - 1);
      }
    });

    input.addEventListener('paste', () => {
      setTimeout(() => {
        const val = input.value;
        if (val && val.includes(',')) {
          addPantryIngredient(val);
          input.value = '';
        }
      }, 10);
    });

    input.addEventListener('blur', () => {
      const val = input.value;
      if (val && val.trim()) {
        addPantryIngredient(val);
        input.value = '';
      }
    });
  }

  function focusPantryInput() {
    const input = document.getElementById('pantry-tags-input');
    if (input) input.focus();
  }

  function renderPantryTags() {
    const container = document.getElementById('pantry-pills-container');
    const clearBtn = document.getElementById('btn-clear-pantry');
    if (!container) return;

    let html = '';
    appState.pantryIngredients.forEach((item, idx) => {
      html += `
        <div class="pantry-pill" data-index="${idx}">
          <span class="pantry-pill-icon">🥕</span>
          <span class="pantry-pill-text">${escapeHtml(item)}</span>
          <button type="button" class="pantry-pill-remove" onclick="removePantryIngredient(${idx}, event)" title="Remove '${escapeJSString(item)}'">✕</button>
        </div>
      `;
    });
    container.innerHTML = html;

    if (clearBtn) {
      clearBtn.style.display = appState.pantryIngredients.length > 0 ? 'inline-block' : 'none';
    }
  }

  function addPantryIngredient(rawName) {
    if (!rawName) return;
    const parts = String(rawName).split(',');
    let addedAny = false;

    parts.forEach(part => {
      const trimmed = part.trim();
      if (!trimmed) return;
      // Case-insensitive duplicate check
      const lower = trimmed.toLowerCase();
      const exists = appState.pantryIngredients.some(p => p.toLowerCase() === lower);
      if (!exists) {
        appState.pantryIngredients.push(trimmed);
        addedAny = true;
      }
    });

    if (addedAny) {
      savePantryIngredientsToStorage();
      renderPantryTags();
      if (appState.db.mealPlan && appState.db.mealPlan.recipes && appState.db.mealPlan.recipes.length > 0) {
        renderMealPlan();
      }
    }
  }

  function removePantryIngredient(idx, event) {
    if (event) event.stopPropagation();
    if (idx >= 0 && idx < appState.pantryIngredients.length) {
      appState.pantryIngredients.splice(idx, 1);
      savePantryIngredientsToStorage();
      renderPantryTags();
      if (appState.db.mealPlan && appState.db.mealPlan.recipes && appState.db.mealPlan.recipes.length > 0) {
        renderMealPlan();
      }
    }
  }

  function clearAllPantryIngredients() {
    appState.pantryIngredients = [];
    savePantryIngredientsToStorage();
    renderPantryTags();
    if (appState.db.mealPlan && appState.db.mealPlan.recipes && appState.db.mealPlan.recipes.length > 0) {
      renderMealPlan();
    }
    showToast("Cleared on-hand pantry ingredients.");
  }

  function savePantryIngredientsToStorage() {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('meal_planner_pantry_ingredients', JSON.stringify(appState.pantryIngredients));
      }
    } catch (e) { }
  }

  function loadPantryIngredientsFromStorage() {
    try {
      if (typeof localStorage !== 'undefined') {
        const stored = localStorage.getItem('meal_planner_pantry_ingredients');
        if (stored) {
          const parsed = JSON.parse(stored);
          if (Array.isArray(parsed)) return parsed;
        }
      }
    } catch (e) { }
    return [];
  }

  function isPantryItemMatch(ingredientName, pantryList) {
    if (!ingredientName || !pantryList || !pantryList.length) return false;
    const cleanIng = ingredientName.toLowerCase().trim();
    return pantryList.some(p => {
      const cleanP = p.toLowerCase().trim();
      if (!cleanP) return false;
      if (cleanIng.includes(cleanP) || cleanP.includes(cleanIng)) return true;
      const stopWords = ['and', 'the', 'for', 'with', 'half', 'some', 'cups', 'cup', 'tbsp', 'tsp', 'lbs', 'can', 'cans', 'cloves', 'pinch', 'slices', 'slice'];
      const words = cleanP.split(/\s+/).filter(w => w.length > 2 && !stopWords.includes(w));
      return words.some(w => cleanIng.includes(w));
    });
  }

  function getMatchedPantryItemsForRecipe(recipe, pantryList) {
    if (!recipe || !Array.isArray(recipe.ingredients) || !pantryList || !pantryList.length) return [];
    const matched = new Set();
    const stopWords = ['and', 'the', 'for', 'with', 'half', 'some', 'cups', 'cup', 'tbsp', 'tsp', 'lbs', 'can', 'cans', 'cloves', 'pinch', 'slices', 'slice'];
    recipe.ingredients.forEach(ing => {
      const cleanIng = (ing && ing.name) ? ing.name.toLowerCase().trim() : "";
      pantryList.forEach(p => {
        const cleanP = p.toLowerCase().trim();
        if (!cleanP) return;
        if (cleanIng.includes(cleanP) || cleanP.includes(cleanIng)) {
          matched.add(p);
        } else {
          const words = cleanP.split(/\s+/).filter(w => w.length > 2 && !stopWords.includes(w));
          if (words.some(w => cleanIng.includes(w))) {
            matched.add(p);
          }
        }
      });
    });
    return Array.from(matched);
  }

  /**
   * Toggle locked state for an individual recipe card
   */
  function handleToggleRecipeLock(event, idx) {
    if (event) event.stopPropagation();
    if (appState.lockedIndices.has(idx)) {
      appState.lockedIndices.delete(idx);
    } else {
      appState.lockedIndices.add(idx);
    }

    // Update db state in memory
    if (appState.db.mealPlan) {
      appState.db.mealPlan.lockedIndices = Array.from(appState.lockedIndices);
    }

    renderMealPlan();
    const recipeName = (appState.db.mealPlan && appState.db.mealPlan.recipes && appState.db.mealPlan.recipes[idx])
      ? appState.db.mealPlan.recipes[idx].name
      : `Recipe #${idx + 1}`;

    if (appState.lockedIndices.has(idx)) {
      showToast(`🔒 Locked "${recipeName}" (preserved during regeneration).`);
    } else {
      showToast(`🔓 Unlocked "${recipeName}".`);
    }
  }

  /**
   * Re-roll or swap an individual recipe at target index with inline card loader
   */
  function handleRerollSingleRecipe(event, idx) {
    if (event) event.stopPropagation();
    if (!appState.db.mealPlan || !appState.db.mealPlan.recipes || !appState.db.mealPlan.recipes[idx]) return;

    if (!appState.hasApiKey) {
      showToast("Please configure an API Key in Settings first.", true);
      switchView('settings');
      return;
    }

    const card = document.getElementById(`recipe-${idx}`);
    if (card) {
      card.classList.add('rerolling');
      let overlay = card.querySelector('.card-reroll-overlay');
      if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'card-reroll-overlay';
        overlay.innerHTML = `
          <div class="card-reroll-spinner"></div>
          <div class="card-reroll-text">Finding replacement recipe...</div>
        `;
        card.appendChild(overlay);
      }
    }

    const planPreferences = els.planPreferencesInput ? els.planPreferencesInput.value.trim() : "";
    const selectedTagsList = Array.from(appState.selectedTags);
    const currentRecipes = appState.db.mealPlan.recipes;
    const oldRecipeName = currentRecipes[idx].name;
    const pantryList = appState.pantryIngredients || [];

    google.script.run
      .withSuccessHandler(res => {
        if (card) card.classList.remove('rerolling');
        appState.db = res.db;
        renderMealPlan();
        showToast(`🔄 Replaced "${oldRecipeName}" with "${res.newRecipe.name}"!`);
      })
      .withFailureHandler(err => {
        if (card) {
          card.classList.remove('rerolling');
          const overlay = card.querySelector('.card-reroll-overlay');
          if (overlay) overlay.remove();
        }
        showToast("Failed to swap recipe: " + err.message, true);
      })
      .rerollSingleRecipeServer(idx, currentRecipes, planPreferences, selectedTagsList, pantryList);
  }

  /**
   * Render the Cuisine Preferences grid (12 cuisines in 2 columns of 6)
   */
  function renderCuisineGrid() {
    if (!els.cuisineGrid) return;

    let html = "";
    CUISINES.forEach(c => {
      const currentPref = (appState.cuisinePreferences && appState.cuisinePreferences[c.name]) || "neutral";
      const statusClass = currentPref === 'prefer' ? 'status-prefer' : (currentPref === 'avoid' ? 'status-avoid' : '');

      html += `
        <div class="cuisine-card ${statusClass}" id="cuisine-card-${escapeHtmlId(c.name)}">
          <div class="cuisine-info" title="${escapeHtml(c.name)}">
            <span class="cuisine-icon">${c.icon}</span>
            <span>${escapeHtml(c.name)}</span>
          </div>
          <div class="cuisine-toggle-group">
            <button type="button" class="cuisine-btn ${currentPref === 'prefer' ? 'active-prefer' : ''}" 
              onclick="setCuisinePreference('${escapeJSString(c.name)}', 'prefer')">Prefer</button>
            <button type="button" class="cuisine-btn ${currentPref === 'neutral' ? 'active-neutral' : ''}" 
              onclick="setCuisinePreference('${escapeJSString(c.name)}', 'neutral')">None</button>
            <button type="button" class="cuisine-btn ${currentPref === 'avoid' ? 'active-avoid' : ''}" 
              onclick="setCuisinePreference('${escapeJSString(c.name)}', 'avoid')">Avoid</button>
          </div>
        </div>
      `;
    });

    els.cuisineGrid.innerHTML = html;
  }

  /**
   * Set cuisine preference ('prefer' | 'avoid' | 'neutral')
   */
  function setCuisinePreference(cuisineName, preferenceState) {
    if (!appState.cuisinePreferences) {
      appState.cuisinePreferences = {};
    }
    if (preferenceState === 'neutral') {
      delete appState.cuisinePreferences[cuisineName];
    } else {
      appState.cuisinePreferences[cuisineName] = preferenceState;
    }
    renderCuisineGrid();
  }

  /**
   * Reset all cuisine preferences to neutral
   */
  function handleResetCuisines() {
    appState.cuisinePreferences = {};
    renderCuisineGrid();
    showToast("Cuisine preferences reset to neutral.");
  }

  /**
   * Escape HTML entities
   */
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  /**
   * Escape string for inline JS function arguments
   */
  function escapeJSString(str) {
    if (!str) return "";
    return String(str)
      .replace(/\\/g, () => "\\\\")
      .replace(/'/g, () => "\\'")
      .replace(/"/g, () => '\\"')
      .replace(/\n/g, () => "\\n")
      .replace(/\r/g, () => "\\r");
  }

  /**
   * Calculate human-friendly total time badge text (e.g. '⏱️ 35m' or '⏱️ 1h 15m')
   */
  function calculateTotalTime(prepTime, cookTime) {
    function parseMinutes(timeStr) {
      if (!timeStr) return 0;
      let mins = 0;
      const str = String(timeStr).toLowerCase();

      // Check for hours e.g. "1 hr", "1.5 hours", "2 hrs"
      const hrMatch = str.match(/(\d+(?:\.\d+)?)\s*(?:hr|hour)/);
      if (hrMatch) {
        mins += parseFloat(hrMatch[1]) * 60;
      }

      // Check for minutes e.g. "25 mins", "30 min", "15m"
      const minMatch = str.match(/(\d+)\s*(?:min|m\b)/);
      if (minMatch) {
        mins += parseInt(minMatch[1], 10);
      } else if (!hrMatch) {
        // Just a plain number e.g. "25"
        const numMatch = str.match(/(\d+)/);
        if (numMatch) mins += parseInt(numMatch[1], 10);
      }
      return mins;
    }

    const totalMinutes = Math.round(parseMinutes(prepTime) + parseMinutes(cookTime));
    if (totalMinutes <= 0) {
      if (prepTime || cookTime) return `⏱️ ${escapeHtml(prepTime || cookTime)}`;
      return "⏱️ 25m";
    }

    if (totalMinutes < 60) {
      return `⏱️ ${totalMinutes}m`;
    }
    const hours = Math.floor(totalMinutes / 60);
    const remainingMins = totalMinutes % 60;
    return remainingMins > 0 ? `⏱️ ${hours}h ${remainingMins}m` : `⏱️ ${hours}h`;
  }

  /**
   * Escape string for DOM element ID
   */
  function escapeHtmlId(str) {
    return String(str).replace(/[^a-zA-Z0-9]/g, "-").toLowerCase();
  }

  /* ==========================================================================
     MPA-13: Interactive In-App Grocery Checklist & Aisle Sorting
     ========================================================================== */
  const AISLE_CATEGORIES = [
    '🥬 Produce',
    '🥩 Meat & Seafood',
    '🧀 Dairy & Refrigerated',
    '🥫 Pantry & Canned',
    '🧂 Spices & Baking'
  ];

  /**
   * Categorizes an ingredient by grocery store aisle / department.
   */
  function categorizeIngredient(rawName) {
    const name = (rawName || "").toLowerCase().trim();
    if (!name) return '🥫 Pantry & Canned';

    // 1. Broths, Stocks, Oils, Sauces, Vinegars, Canned Goods -> Pantry & Canned
    if (/broth|stock|bouillon|olive oil|vegetable oil|sesame oil|canola oil|cooking spray|vinegar|soy sauce|tamari|worcestershire|fish sauce|hot sauce|sriracha|salsa|tomato sauce|tomato paste|marinara|canned|beans|diced tomato|crushed tomato|coconut milk|peanut butter|honey|maple syrup|mayo|mustard|ketchup|dressing/.test(name)) {
      return '🥫 Pantry & Canned';
    }

    // 2. Spices, Powders, Seasonings, Baking
    if (/powder|seasoning|rub\b|extract|sugar|flour|cornstarch|baking|cocoa|yeast|cinnamon|nutmeg|paprika|cumin|turmeric|coriander|curry powder|cardamom|cayenne|allspice|vanilla|chocolate chip|red pepper flake|chili flake/.test(name)) {
      return '🧂 Spices & Baking';
    }
    if (/\bsalt\b|\bpepper\b|\bpeppercorn\b|\bpeppercorns\b|\bkosher salt\b|\bsea salt\b|\bblack pepper\b/.test(name) && !/bell pepper|chili pepper|jalapeno|poblano|serrano|sweet pepper|banana pepper/.test(name)) {
      return '🧂 Spices & Baking';
    }

    // 3. Meat & Seafood
    if (/chicken|beef|steak|pork|turkey|duck|lamb|veal|bacon|pancetta|prosciutto|sausage|chorizo|ham\b|ribeye|sirloin|ground beef|ground turkey|ground pork|salmon|tuna\b|shrimp|prawn|fish|cod\b|tilapia|halibut|mahi|trout|crab|lobster|scallop|clam|mussel|calamari|squid|anchov|meat/.test(name)) {
      return '🥩 Meat & Seafood';
    }

    // 4. Dairy & Refrigerated (and plant-based dairy substitutes)
    if (/milk|butter|cheese|cheddar|mozzarella|parmesan|parmigiano|ricotta|feta|gouda|swiss|provolone|brie|pecorino|yogurt|cream|sour cream|half and half|half & half|egg|eggs|egg white|egg yolk|tofu|tempeh|ghee|margarine|cream cheese|cottage cheese|mascarpone|queso/.test(name)) {
      return '🧀 Dairy & Refrigerated';
    }

    // 5. Fresh Produce
    if (/garlic|onion|shallot|leek|scallion|ginger|tomato|potato|potatoes|sweet potato|lettuce|spinach|kale|arugula|cabbage|bok choy|chard|celery|carrot|bell pepper|jalapeno|chili|poblano|serrano|avocado|cucumber|zucchini|squash|broccoli|cauliflower|asparagus|mushroom|green bean|pea\b|peas\b|snap pea|snow pea|eggplant|corn\b|radish|beet|lemon|lime|orange|apple|banana|berry|berries|strawberry|blueberry|raspberry|blackberry|mango|pineapple|grape|peach|pear|melon|watermelon|cilantro|parsley|basil|rosemary|thyme|mint|dill|sage\b|tarragon|lemongrass|sprout|herb/.test(name)) {
      return '🥬 Produce';
    }

    // 6. Grains, Pasta, Bread, Canned & Pantry fallback
    if (/pasta|spaghetti|penne|noodle|rice|quinoa|oat|bread|tortilla|pita|cracker|panko|breadcrumb|chip|olive|caper|nut\b|nuts\b|almond|walnut|peanut|cashew|pecan|pine nut|seed|sunflower|sesame/.test(name)) {
      return '🥫 Pantry & Canned';
    }

    // Default fallback
    return '🥫 Pantry & Canned';
  }

  /**
   * Consolidate and deduplicate ingredients client-side
   */
  function consolidateShoppingListClient(recipes) {
    if (!Array.isArray(recipes)) return [];
    const list = {};
    recipes.forEach(recipe => {
      if (!recipe.ingredients) return;
      recipe.ingredients.forEach(ing => {
        const name = (ing.name || "").toLowerCase().trim();
        if (!name) return;
        const amount = parseFloat(ing.amount) || 0;
        const unit = (ing.unit || "").toLowerCase().trim();
        if (!list[name]) list[name] = [];
        list[name].push({ amount, unit });
      });
    });

    const consolidated = [];
    for (const name in list) {
      const items = list[name];
      const merged = [];
      items.forEach(item => {
        let found = false;
        for (let i = 0; i < merged.length; i++) {
          if (merged[i].unit === item.unit) {
            merged[i].amount = Math.round((merged[i].amount + item.amount) * 100) / 100;
            found = true;
            break;
          }
        }
        if (!found) {
          merged.push({ amount: Math.round(item.amount * 100) / 100, unit: item.unit });
        }
      });
      consolidated.push({
        name: name,
        category: categorizeIngredient(name),
        amounts: merged
      });
    }

    consolidated.sort((a, b) => a.name.localeCompare(b.name));
    return consolidated;
  }

  /**
   * Key for localStorage persistence of checklist states
   */
  function getShoppingChecklistStorageKey(plan) {
    const planId = plan && (plan.generatedAt || (plan.executionResult && plan.executionResult.shoppingListDocName) || 'active');
    return 'mp_checklist_' + String(planId).replace(/[^a-zA-Z0-9]/g, '_');
  }

  function getStoredShoppingChecklist(plan) {
    try {
      const key = getShoppingChecklistStorageKey(plan);
      const raw = localStorage.getItem(key);
      if (!raw) return new Set();
      const parsed = JSON.parse(raw);
      return new Set(Array.isArray(parsed) ? parsed : []);
    } catch (e) {
      return new Set();
    }
  }

  function saveStoredShoppingChecklist(plan, checkedSet) {
    try {
      const key = getShoppingChecklistStorageKey(plan);
      localStorage.setItem(key, JSON.stringify(Array.from(checkedSet)));
    } catch (e) {
      console.warn("Could not save checklist state to localStorage: ", e);
    }
  }

  /* ==========================================================================
     MPA-21: PWA & Offline Grocery Mode Helpers & Local Cache
     ========================================================================== */
  const OFFLINE_PLAN_CACHE_KEY = 'mp_active_plan_cache';

  function getCustomGroceryStorageKey(plan) {
    const planId = plan && (plan.generatedAt || (plan.executionResult && plan.executionResult.shoppingListDocName) || 'active');
    return 'mp_custom_grocery_items_' + String(planId).replace(/[^a-zA-Z0-9]/g, '_');
  }

  function getStoredCustomGroceryItems(plan) {
    try {
      const key = getCustomGroceryStorageKey(plan);
      const raw = localStorage.getItem(key);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function saveStoredCustomGroceryItems(plan, items) {
    try {
      const key = getCustomGroceryStorageKey(plan);
      localStorage.setItem(key, JSON.stringify(Array.isArray(items) ? items : []));
    } catch (e) {
      console.warn("Could not save custom grocery items to localStorage: ", e);
    }
  }

  function cacheActivePlanLocally(plan) {
    if (!plan) return;
    try {
      localStorage.setItem(OFFLINE_PLAN_CACHE_KEY, JSON.stringify(plan));
    } catch (e) {
      console.warn("Could not cache active plan to localStorage:", e);
    }
  }

  function restorePlanFromOfflineCache() {
    try {
      const raw = localStorage.getItem(OFFLINE_PLAN_CACHE_KEY);
      if (!raw) return false;
      const plan = JSON.parse(raw);
      if (plan && plan.recipes && plan.recipes.length > 0) {
        appState.db.mealPlan = plan;
        renderMealPlan();
        return true;
      }
    } catch (e) {
      console.warn("Could not restore plan from offline cache:", e);
    }
    return false;
  }

  function initOfflineStorage() {
    if (!appState.db.mealPlan) {
      restorePlanFromOfflineCache();
    }
  }

  function initNetworkListeners() {
    updateNetworkStatusUI(typeof navigator !== 'undefined' ? navigator.onLine !== false : true);

    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => {
        updateNetworkStatusUI(true);
        showToast("🟢 Connected to network. Syncing data...", false);
        syncOfflineChecklistToServer();
      });

      window.addEventListener('offline', () => {
        updateNetworkStatusUI(false);
        showToast("⚡ Offline Grocery Mode: Using local offline cache.", false);
      });
    }
  }

  function updateNetworkStatusUI(isOnline) {
    appState.isOnline = isOnline;
    const pill = document.getElementById('network-status-pill');
    const label = document.getElementById('network-status-label');
    if (!pill || !label) return;

    if (isOnline) {
      pill.classList.remove('offline');
      pill.classList.add('online');
      pill.title = "Network status: Online";
      label.textContent = "Online";
    } else {
      pill.classList.remove('online');
      pill.classList.add('offline');
      pill.title = "Network status: Offline Mode (Working from local cache)";
      label.textContent = "Offline Mode";
    }
  }

  function syncOfflineChecklistToServer() {
    const plan = appState.db.mealPlan;
    if (!plan) return;
    if (typeof navigator !== 'undefined' && !navigator.onLine) return;
    if (typeof google === 'undefined' || !google.script || !google.script.run) return;

    const checkedSet = getStoredShoppingChecklist(plan);
    const checkedArray = Array.from(checkedSet);
    const customItems = getStoredCustomGroceryItems(plan);

    google.script.run
      .withSuccessHandler(res => {
        console.log("Synchronized shopping checklist with Drive DB:", res);
      })
      .withFailureHandler(err => {
        console.warn("Background sync of shopping checklist deferred:", err);
      })
      .syncShoppingChecklistServer(checkedArray, customItems);
  }

  /**
   * Consolidates shopping list including custom ad-hoc user items
   */
  function getConsolidatedShoppingList(plan) {
    if (!plan) return [];
    const baseList = (plan.executionResult && plan.executionResult.shoppingList) ||
      plan.shoppingList ||
      consolidateShoppingListClient(plan.recipes);

    const result = (baseList || []).map(item => ({
      name: item.name,
      category: item.category || categorizeIngredient(item.name),
      amounts: item.amounts ? item.amounts.slice() : []
    }));

    const customItems = getStoredCustomGroceryItems(plan);
    customItems.forEach(custom => {
      const existing = result.find(r => r.name.toLowerCase() === custom.name.toLowerCase());
      if (existing) {
        if (custom.amount) {
          existing.amounts.push({ amount: custom.amount, unit: custom.unit || 'item' });
        }
      } else {
        result.push({
          name: custom.name,
          category: custom.category || categorizeIngredient(custom.name),
          amounts: custom.amount ? [{ amount: custom.amount, unit: custom.unit || 'item' }] : [],
          isCustom: true
        });
      }
    });

    result.sort((a, b) => a.name.localeCompare(b.name));
    return result;
  }

  /**
   * Screen Wake Lock Controller
   */
  let wakeLockSentinel = null;

  async function requestWakeLock() {
    if (typeof navigator !== 'undefined' && 'wakeLock' in navigator && typeof navigator.wakeLock.request === 'function') {
      try {
        wakeLockSentinel = await navigator.wakeLock.request('screen');
        wakeLockSentinel.addEventListener('release', () => {
          updateWakeLockUI(false);
        });
        updateWakeLockUI(true);
      } catch (err) {
        console.warn("Screen Wake Lock request was not granted:", err);
        updateWakeLockUI(false);
      }
    } else {
      updateWakeLockUI(false);
    }
  }

  function releaseWakeLock() {
    if (wakeLockSentinel) {
      try {
        wakeLockSentinel.release();
      } catch (e) { }
      wakeLockSentinel = null;
    }
    updateWakeLockUI(false);
  }

  function updateWakeLockUI(isActive) {
    const badge = document.getElementById('grocery-wakelock-badge');
    if (!badge) return;
    if (isActive) {
      badge.classList.remove('inactive');
      badge.classList.add('active');
      badge.innerHTML = `<span>☀️ Screen Awake</span>`;
      badge.title = "Screen stays awake while shopping";
    } else {
      badge.classList.remove('active');
      badge.classList.add('inactive');
      badge.innerHTML = `<span>🌙 Auto-Sleep</span>`;
      badge.title = "Screen will auto-sleep normally";
    }
  }

  /**
   * Render HTML markup for the In-App Interactive Grocery Checklist
   */
  function renderShoppingListHtml(plan) {
    if (!plan) return '';
    const shoppingList = getConsolidatedShoppingList(plan);

    if (!shoppingList || shoppingList.length === 0) return '';

    const checkedSet = getStoredShoppingChecklist(plan);
    const totalItems = shoppingList.length;
    let checkedCount = 0;

    // Group items by category
    const categorized = {};
    AISLE_CATEGORIES.forEach(cat => { categorized[cat] = []; });

    shoppingList.forEach(item => {
      const cat = item.category || categorizeIngredient(item.name);
      if (!categorized[cat]) categorized[cat] = [];
      categorized[cat].push(item);
      if (checkedSet.has(item.name)) {
        checkedCount++;
      }
    });

    const progressPct = totalItems > 0 ? Math.round((checkedCount / totalItems) * 100) : 0;

    let categoriesHtml = '';
    AISLE_CATEGORIES.forEach(cat => {
      const items = categorized[cat] || [];
      if (items.length === 0) return;

      const catCheckedCount = items.filter(it => checkedSet.has(it.name)).length;
      const catTotal = items.length;
      const catSlug = escapeHtmlId(cat);

      let itemsHtml = '';
      items.forEach(item => {
        const isChecked = checkedSet.has(item.name);
        const amountsStr = (item.amounts || []).map(a => `${a.amount} ${a.unit}`).join(', ');
        const itemSlug = escapeHtmlId(item.name);

        itemsHtml += `
          <div class="shopping-item-row ${isChecked ? 'checked' : ''}" 
               id="shop-row-${itemSlug}"
               onclick="handleToggleShoppingItem(event, '${escapeJSString(item.name)}')">
            <label class="shopping-checkbox-label" onclick="event.stopPropagation()">
              <input type="checkbox" class="shopping-item-checkbox" 
                     id="shop-check-${itemSlug}" 
                     ${isChecked ? 'checked' : ''} 
                     onchange="handleToggleShoppingItemCheckbox('${escapeJSString(item.name)}', this.checked)">
              <span class="shopping-custom-checkbox"></span>
            </label>
            <div class="shopping-item-content">
              <span class="shopping-item-name">${escapeHtml(item.name)}</span>
              <span class="shopping-item-amount">${escapeHtml(amountsStr)}</span>
            </div>
          </div>
        `;
      });

      categoriesHtml += `
        <div class="shopping-category-card" id="shop-cat-${catSlug}">
          <div class="shopping-category-header" onclick="handleToggleShoppingCategory('${catSlug}')">
            <div class="shopping-category-title-group">
              <span class="shopping-category-name">${escapeHtml(cat)}</span>
              <span class="shopping-category-count" id="cat-count-${catSlug}">
                ${catTotal} ${catTotal === 1 ? 'item' : 'items'} (${catCheckedCount} checked)
              </span>
            </div>
            <span class="shopping-category-chevron">▼</span>
          </div>
          <div class="shopping-items-list" id="items-list-${catSlug}">
            ${itemsHtml}
          </div>
        </div>
      `;
    });

    return `
      <div class="shopping-list-panel" id="shopping-list-section">
        <div class="shopping-list-header">
          <div class="shopping-list-header-left">
            <div class="shopping-list-title-row">
              <span class="shopping-list-icon">🛒</span>
              <h3 class="shopping-list-title">Interactive Grocery Checklist</h3>
              <span class="shopping-list-badge" id="shopping-list-progress-badge">
                ${checkedCount} of ${totalItems} checked (${progressPct}%)
              </span>
            </div>
            <p class="shopping-list-subtitle">
              Aisle-sorted checklist for walking supermarket aisles or pantry pre-checks. Check off items with instant strike-through.
            </p>
          </div>
          <div class="shopping-list-actions">
            <button type="button" class="btn btn-sm" id="btn-open-grocery-mode" onclick="handleOpenGroceryMode()" style="background: var(--accent-primary); color: #ffffff; font-weight: 600;">
              <span class="btn-icon">🛒</span>
              <span>Enter Grocery Mode</span>
            </button>
            <button type="button" class="btn btn-gold btn-sm" id="btn-copy-shopping-list" onclick="handleCopyShoppingList()">
              <span class="btn-icon">📋</span>
              <span id="btn-copy-shopping-text">Copy for Notes</span>
            </button>
            <button type="button" class="btn btn-secondary btn-sm" id="btn-reset-shopping-checklist" onclick="handleResetShoppingChecklist()">
              <span class="btn-icon">↺</span>
              <span>Reset Checks</span>
            </button>
            <button type="button" class="btn btn-secondary btn-sm" id="btn-toggle-all-categories" onclick="handleToggleAllShoppingCategories()">
              <span id="toggle-all-cat-label">Collapse All</span>
            </button>
          </div>
        </div>

        <div class="shopping-progress-bar-container">
          <div class="shopping-progress-bar" id="shopping-progress-bar" style="width: ${progressPct}%;"></div>
        </div>

        <div class="shopping-categories-container">
          ${categoriesHtml}
        </div>
      </div>
    `;
  }

  /**
   * Toggle checked state for a shopping list item by clicking row
   */
  function handleToggleShoppingItem(event, itemName) {
    if (event) event.stopPropagation();
    const plan = appState.db.mealPlan;
    if (!plan) return;
    const checkedSet = getStoredShoppingChecklist(plan);
    const isCurrentlyChecked = checkedSet.has(itemName);
    const nextState = !isCurrentlyChecked;

    if (nextState) {
      checkedSet.add(itemName);
    } else {
      checkedSet.delete(itemName);
    }
    saveStoredShoppingChecklist(plan, checkedSet);

    // Update DOM row & checkbox for standard list
    const itemSlug = escapeHtmlId(itemName);
    const rowEl = document.getElementById(`shop-row-${itemSlug}`);
    const checkEl = document.getElementById(`shop-check-${itemSlug}`);
    if (rowEl) rowEl.classList.toggle('checked', nextState);
    if (checkEl) checkEl.checked = nextState;

    // Update DOM row & checkbox for Grocery Mode if active
    const gRowEl = document.getElementById(`grocery-row-${itemSlug}`);
    const gCheckEl = document.getElementById(`grocery-check-${itemSlug}`);
    if (gRowEl) gRowEl.classList.toggle('checked', nextState);
    if (gCheckEl) gCheckEl.checked = nextState;

    updateShoppingListProgressUI(plan, checkedSet);
    if (appState.groceryModeState && appState.groceryModeState.active) {
      updateGroceryModeStatsAndPills();
    }
    syncOfflineChecklistToServer();
  }

  /**
   * Direct change event from item checkbox input
   */
  function handleToggleShoppingItemCheckbox(itemName, isChecked) {
    const plan = appState.db.mealPlan;
    if (!plan) return;
    const checkedSet = getStoredShoppingChecklist(plan);
    if (isChecked) {
      checkedSet.add(itemName);
    } else {
      checkedSet.delete(itemName);
    }
    saveStoredShoppingChecklist(plan, checkedSet);

    const itemSlug = escapeHtmlId(itemName);
    const rowEl = document.getElementById(`shop-row-${itemSlug}`);
    const checkEl = document.getElementById(`shop-check-${itemSlug}`);
    if (rowEl) rowEl.classList.toggle('checked', isChecked);
    if (checkEl) checkEl.checked = isChecked;

    const gRowEl = document.getElementById(`grocery-row-${itemSlug}`);
    const gCheckEl = document.getElementById(`grocery-check-${itemSlug}`);
    if (gRowEl) gRowEl.classList.toggle('checked', isChecked);
    if (gCheckEl) gCheckEl.checked = isChecked;

    updateShoppingListProgressUI(plan, checkedSet);
    if (appState.groceryModeState && appState.groceryModeState.active) {
      updateGroceryModeStatsAndPills();
    }
    syncOfflineChecklistToServer();
  }

  /**
   * Update progress bar, badges, and category item counts
   */
  function updateShoppingListProgressUI(plan, checkedSet) {
    const shoppingList = getConsolidatedShoppingList(plan);
    if (!shoppingList) return;

    const totalItems = shoppingList.length;
    let checkedCount = 0;

    const categorized = {};
    AISLE_CATEGORIES.forEach(cat => { categorized[cat] = []; });
    shoppingList.forEach(item => {
      const cat = item.category || categorizeIngredient(item.name);
      if (!categorized[cat]) categorized[cat] = [];
      categorized[cat].push(item);
      if (checkedSet.has(item.name)) checkedCount++;
    });

    const progressPct = totalItems > 0 ? Math.round((checkedCount / totalItems) * 100) : 0;

    const barEl = document.getElementById('shopping-progress-bar');
    if (barEl) barEl.style.width = `${progressPct}%`;

    const badgeEl = document.getElementById('shopping-list-progress-badge');
    if (badgeEl) badgeEl.textContent = `${checkedCount} of ${totalItems} checked (${progressPct}%)`;

    AISLE_CATEGORIES.forEach(cat => {
      const items = categorized[cat] || [];
      if (items.length === 0) return;
      const catSlug = escapeHtmlId(cat);
      const catCheckedCount = items.filter(it => checkedSet.has(it.name)).length;
      const countEl = document.getElementById(`cat-count-${catSlug}`);
      if (countEl) {
        countEl.textContent = `${items.length} ${items.length === 1 ? 'item' : 'items'} (${catCheckedCount} checked)`;
      }
    });
  }

  /**
   * Expand / Collapse an individual category accordion
   */
  function handleToggleShoppingCategory(catSlug) {
    const cardEl = document.getElementById(`shop-cat-${catSlug}`);
    if (cardEl) {
      cardEl.classList.toggle('collapsed');
    }
  }

  /**
   * Expand / Collapse all categories at once
   */
  let allShoppingCatsCollapsed = false;
  function handleToggleAllShoppingCategories() {
    allShoppingCatsCollapsed = !allShoppingCatsCollapsed;
    const cards = document.querySelectorAll('.shopping-category-card');
    cards.forEach(card => {
      card.classList.toggle('collapsed', allShoppingCatsCollapsed);
    });
    const labelEl = document.getElementById('toggle-all-cat-label');
    if (labelEl) {
      labelEl.textContent = allShoppingCatsCollapsed ? 'Expand All' : 'Collapse All';
    }
  }

  /**
   * Reset all checks for the active plan's checklist
   */
  function handleResetShoppingChecklist() {
    const plan = appState.db.mealPlan;
    if (!plan) return;
    const emptySet = new Set();
    saveStoredShoppingChecklist(plan, emptySet);

    const rows = document.querySelectorAll('.shopping-item-row');
    rows.forEach(r => r.classList.remove('checked'));
    const checkboxes = document.querySelectorAll('.shopping-item-checkbox');
    checkboxes.forEach(c => { c.checked = false; });

    updateShoppingListProgressUI(plan, emptySet);
    if (appState.groceryModeState && appState.groceryModeState.active) {
      updateGroceryModeStatsAndPills();
    }
    showToast("Checklist items reset!");
    syncOfflineChecklistToServer();
  }

  /**
   * Fullscreen Grocery Mode Controller Functions (MPA-21)
   */
  function handleOpenGroceryMode() {
    const plan = appState.db.mealPlan;
    if (!plan) {
      showToast("No active meal plan to shop for.", true);
      return;
    }

    appState.groceryModeState.active = true;
    const modal = document.getElementById('grocery-mode-modal');
    if (modal) modal.style.display = 'flex';

    requestWakeLock();
    renderGroceryModeContent();

    if (typeof document !== 'undefined' && document.body) {
      document.body.style.overflow = 'hidden';
    }
  }

  function handleCloseGroceryMode() {
    appState.groceryModeState.active = false;
    const modal = document.getElementById('grocery-mode-modal');
    if (modal) modal.style.display = 'none';

    releaseWakeLock();
    if (typeof document !== 'undefined' && document.body) {
      document.body.style.overflow = '';
    }

    const plan = appState.db.mealPlan;
    if (plan) {
      const checkedSet = getStoredShoppingChecklist(plan);
      updateShoppingListProgressUI(plan, checkedSet);
    }
  }

  function handleToggleHideChecked(isChecked) {
    appState.groceryModeState.hideChecked = !!isChecked;
    const content = document.getElementById('grocery-mode-content');
    if (content) {
      content.classList.toggle('hide-checked', appState.groceryModeState.hideChecked);
    }
    const toggle = document.getElementById('grocery-hide-checked-toggle');
    if (toggle) toggle.checked = appState.groceryModeState.hideChecked;
  }

  function handleFilterGroceryAisle(category) {
    appState.groceryModeState.selectedCategory = category || 'all';
    renderGroceryModeContent();
  }

  function handleAddCustomGroceryItem(event) {
    if (event) event.preventDefault();
    const input = document.getElementById('grocery-add-input');
    const categorySelect = document.getElementById('grocery-add-category');
    if (!input) return;

    const name = input.value.trim();
    if (!name) return;
    const category = categorySelect ? categorySelect.value : '🥫 Pantry & Canned';

    const plan = appState.db.mealPlan;
    if (!plan) return;

    const customItems = getStoredCustomGroceryItems(plan);
    customItems.push({
      name: name,
      category: category,
      amount: '1',
      unit: 'item'
    });
    saveStoredCustomGroceryItems(plan, customItems);

    input.value = '';
    renderGroceryModeContent();
    const checkedSet = getStoredShoppingChecklist(plan);
    updateShoppingListProgressUI(plan, checkedSet);
    showToast(`Added "${name}" to ${category}!`);
    syncOfflineChecklistToServer();
  }

  function updateGroceryModeStatsAndPills() {
    const plan = appState.db.mealPlan;
    if (!plan) return;

    const shoppingList = getConsolidatedShoppingList(plan);
    const checkedSet = getStoredShoppingChecklist(plan);
    const totalItems = shoppingList.length;
    let totalChecked = 0;

    const categorized = {};
    AISLE_CATEGORIES.forEach(cat => { categorized[cat] = []; });

    shoppingList.forEach(item => {
      const cat = item.category || categorizeIngredient(item.name);
      if (!categorized[cat]) categorized[cat] = [];
      categorized[cat].push(item);
      if (checkedSet.has(item.name)) totalChecked++;
    });

    const progressPct = totalItems > 0 ? Math.round((totalChecked / totalItems) * 100) : 0;
    const statsEl = document.getElementById('grocery-mode-stats');
    if (statsEl) {
      statsEl.textContent = `${totalChecked} of ${totalItems} items checked (${progressPct}% complete)`;
    }

    const aisleBarEl = document.getElementById('grocery-aisle-bar');
    if (aisleBarEl) {
      let pillsHtml = `
        <button type="button" class="grocery-aisle-pill ${appState.groceryModeState.selectedCategory === 'all' ? 'active' : ''}" 
                onclick="handleFilterGroceryAisle('all')">
          <span>🛒 All Items</span>
          <span class="grocery-aisle-pill-count">${totalItems}</span>
        </button>
      `;

      AISLE_CATEGORIES.forEach(cat => {
        const items = categorized[cat] || [];
        if (items.length === 0) return;
        const catChecked = items.filter(it => checkedSet.has(it.name)).length;
        const isSelected = appState.groceryModeState.selectedCategory === cat;
        pillsHtml += `
          <button type="button" class="grocery-aisle-pill ${isSelected ? 'active' : ''}" 
                  onclick="handleFilterGroceryAisle('${escapeJSString(cat)}')">
            <span>${escapeHtml(cat)}</span>
            <span class="grocery-aisle-pill-count">${items.length - catChecked}/${items.length}</span>
          </button>
        `;
      });
      aisleBarEl.innerHTML = pillsHtml;
    }
  }

  function renderGroceryModeContent() {
    const plan = appState.db.mealPlan;
    const contentEl = document.getElementById('grocery-mode-content');
    if (!plan || !contentEl) return;

    const shoppingList = getConsolidatedShoppingList(plan);
    const checkedSet = getStoredShoppingChecklist(plan);

    // Group items by category
    const categorized = {};
    AISLE_CATEGORIES.forEach(cat => { categorized[cat] = []; });

    shoppingList.forEach(item => {
      const cat = item.category || categorizeIngredient(item.name);
      if (!categorized[cat]) categorized[cat] = [];
      categorized[cat].push(item);
    });

    updateGroceryModeStatsAndPills();

    // Render Categorized Shopping Sections
    let sectionsHtml = '';
    AISLE_CATEGORIES.forEach(cat => {
      if (appState.groceryModeState.selectedCategory !== 'all' && appState.groceryModeState.selectedCategory !== cat) {
        return;
      }
      const items = categorized[cat] || [];
      if (items.length === 0) return;

      const catCheckedCount = items.filter(it => checkedSet.has(it.name)).length;
      const catTotal = items.length;
      const catSlug = escapeHtmlId(cat);

      let itemsHtml = '';
      items.forEach(item => {
        const isChecked = checkedSet.has(item.name);
        const amountsStr = (item.amounts || []).map(a => `${a.amount} ${a.unit}`).join(', ');
        const itemSlug = escapeHtmlId(item.name);

        itemsHtml += `
          <div class="shopping-item-row ${isChecked ? 'checked' : ''}" 
               id="grocery-row-${itemSlug}"
               onclick="handleToggleShoppingItem(event, '${escapeJSString(item.name)}')">
            <label class="shopping-checkbox-label" onclick="event.stopPropagation()">
              <input type="checkbox" class="shopping-item-checkbox" 
                     id="grocery-check-${itemSlug}" 
                     ${isChecked ? 'checked' : ''} 
                     onchange="handleToggleShoppingItemCheckbox('${escapeJSString(item.name)}', this.checked)">
              <span class="shopping-custom-checkbox"></span>
            </label>
            <div class="shopping-item-content">
              <span class="shopping-item-name">${escapeHtml(item.name)}</span>
              <span class="shopping-item-amount">${escapeHtml(amountsStr)}</span>
            </div>
          </div>
        `;
      });

      sectionsHtml += `
        <div class="shopping-category-card" id="grocery-cat-${catSlug}">
          <div class="shopping-category-header">
            <div class="shopping-category-title-group">
              <span class="shopping-category-name">${escapeHtml(cat)}</span>
              <span class="shopping-category-count">
                ${catTotal} ${catTotal === 1 ? 'item' : 'items'} (${catCheckedCount} checked)
              </span>
            </div>
          </div>
          <div class="shopping-items-list">
            ${itemsHtml}
          </div>
        </div>
      `;
    });

    contentEl.innerHTML = sectionsHtml;
    contentEl.classList.toggle('hide-checked', appState.groceryModeState.hideChecked);
  }

  /**
   * Format grocery list as clean plain text / Markdown grouped by aisle
   */
  function formatShoppingListText(plan) {
    const shoppingList = getConsolidatedShoppingList(plan);
    if (!shoppingList || shoppingList.length === 0) return '';

    const categorized = {};
    AISLE_CATEGORIES.forEach(cat => { categorized[cat] = []; });
    shoppingList.forEach(item => {
      const cat = item.category || categorizeIngredient(item.name);
      if (!categorized[cat]) categorized[cat] = [];
      categorized[cat].push(item);
    });

    let text = "🛒 Grocery Shopping List\n\n";
    AISLE_CATEGORIES.forEach(cat => {
      const items = categorized[cat] || [];
      if (items.length > 0) {
        text += `${cat}\n`;
        items.forEach(item => {
          const capName = item.name.charAt(0).toUpperCase() + item.name.slice(1);
          const amountsStr = (item.amounts || []).map(a => `${a.amount} ${a.unit}`).join(', ');
          text += `- ${capName}: ${amountsStr}\n`;
        });
        text += "\n";
      }
    });

    return text.trim();
  }

  /**
   * 1-Click Copy grocery list to clipboard
   */
  function handleCopyShoppingList() {
    const plan = appState.db.mealPlan;
    if (!plan) return;
    const text = formatShoppingListText(plan);
    if (!text) {
      showToast("No grocery items found to copy.", true);
      return;
    }

    const copyText = document.getElementById('btn-copy-shopping-text');

    function onCopySuccess() {
      if (copyText) copyText.textContent = "✓ Copied!";
      showToast("📋 Grocery list copied to clipboard (ready for Notes / Keep / Instacart)!");
      setTimeout(() => {
        if (copyText) copyText.textContent = "Copy for Notes / Instacart";
      }, 2500);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text)
        .then(onCopySuccess)
        .catch(() => fallbackCopyText(text, onCopySuccess));
    } else {
      fallbackCopyText(text, onCopySuccess);
    }
  }

  function fallbackCopyText(text, onSuccess) {
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      const successful = document.execCommand('copy');
      document.body.removeChild(textarea);
      if (successful) {
        if (onSuccess) onSuccess();
      } else {
        showToast("Could not copy list to clipboard.", true);
      }
    } catch (e) {
      showToast("Could not copy list to clipboard.", true);
    }
  }

  function scrollToShoppingList(event) {
    if (event) event.preventDefault();
    const section = document.getElementById('shopping-list-section');
    if (section) {
      section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  /**
   * Update the Gemini API status badge & description
   */
  function updateApiBadge() {
    const status = appState.apiKeyStatus || {
      hasPersonalKey: appState.hasApiKey,
      hasSharedKey: false,
      activeKeyType: appState.hasApiKey ? 'personal' : 'none'
    };

    const descEl = document.getElementById('api-desc');

    if (status.activeKeyType === 'personal') {
      els.apiBadge.className = "api-badge active";
      els.apiBadge.innerHTML = "• Personal Key Active";
      els.apiKeyInput.placeholder = "•••••••••••••••••••••••••••••••• (Personal Key Saved)";
      els.apiKeyInput.value = "";
      if (descEl) {
        descEl.innerHTML = "Using your <strong>personal Gemini API key</strong> (dedicated quota & limits). You can replace it anytime or click <em>Clear Personal Key</em> to revert to the shared starter key.";
      }
    } else if (status.activeKeyType === 'shared') {
      els.apiBadge.className = "api-badge shared";
      els.apiBadge.innerHTML = "• Starter Key Active (Shared)";
      els.apiKeyInput.placeholder = "Paste personal API key to override";
      els.apiKeyInput.value = "";
      if (descEl) {
        descEl.innerHTML = "The app is currently using the <strong>shared starter API key</strong>. You can generate meals right away, or click <em>✨ Create API Key</em> to get your own personal key for dedicated rate limits.";
      }
    } else {
      els.apiBadge.className = "api-badge missing";
      els.apiBadge.innerHTML = "• API Key Missing";
      els.apiKeyInput.placeholder = "Enter your Gemini API key...";
      els.apiKeyInput.value = "";
      if (descEl) {
        descEl.innerHTML = "A Gemini API key is required to run the meal planning models. Click <em>✨ Create API Key</em> to obtain a free key from Google AI Studio, then paste and save it below.";
      }
    }
  }

  /**
   * Save Preferences to Drive
   */
  function handleSavePreferences() {
    const skipPref = (els.settingSkipWelcome && els.settingSkipWelcome.checked) || (els.prefSkipWelcome && els.prefSkipWelcome.checked) || (els.skipWelcomeCheckbox && els.skipWelcomeCheckbox.checked) || false;
    const prefs = {
      allergies: els.prefAllergies ? els.prefAllergies.value.trim() : "",
      dietaryPreferences: els.prefDietaryPreferences ? els.prefDietaryPreferences.value.trim() : "",
      cuisinePreferences: appState.cuisinePreferences || {},
      dinersCount: els.prefDiners ? (parseInt(els.prefDiners.value, 10) || 4) : 4,
      defaultMealTime: els.prefMealTime ? (els.prefMealTime.value.trim() || "5:30pm") : "5:30pm",
      skipWelcomePage: skipPref
    };

    showLoader("Saving preferences...", "Updating your database in Google Drive");

    google.script.run
      .withSuccessHandler(data => {
        hideLoader();
        appState.db = data.db;
        const shouldSkip = !!data.db.preferences.skipWelcomePage;
        if (els.skipWelcomeCheckbox) els.skipWelcomeCheckbox.checked = shouldSkip;
        if (els.settingSkipWelcome) els.settingSkipWelcome.checked = shouldSkip;
        if (els.prefSkipWelcome) els.prefSkipWelcome.checked = shouldSkip;
        try {
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem('meal_planner_skip_welcome', shouldSkip ? 'true' : 'false');
          }
        } catch (e) { }
        showToast("Preferences saved successfully!");
      })
      .withFailureHandler(err => {
        hideLoader();
        showToast("Failed to save preferences: " + err.message, true);
      })
      .savePreferences(prefs);
  }

  /**
   * Toggle skip welcome page preference from hero panel or preferences
   */
  function handleToggleSkipWelcome(isChecked) {
    isChecked = !!isChecked;
    if (els.skipWelcomeCheckbox) els.skipWelcomeCheckbox.checked = isChecked;
    if (els.settingSkipWelcome) els.settingSkipWelcome.checked = isChecked;
    if (els.prefSkipWelcome) els.prefSkipWelcome.checked = isChecked;

    if (!appState.db.preferences) appState.db.preferences = {};
    appState.db.preferences.skipWelcomePage = isChecked;

    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('meal_planner_skip_welcome', isChecked ? 'true' : 'false');
      }
    } catch (e) { }

    google.script.run
      .withSuccessHandler(res => {
        // Preference persisted in Drive database
      })
      .withFailureHandler(err => {
        showToast("Failed to save skip preference: " + err.message, true);
      })
      .setSkipWelcomePreference(isChecked);

    if (isChecked) {
      showToast("Preference saved: skipping welcome page.");
      switchView('planner');
    } else {
      showToast("Preference saved: welcome page will be shown on startup.");
    }
  }

  /**
   * Save API Key to PropertiesService
   */
  function handleSaveApiKey() {
    const key = els.apiKeyInput.value.trim();
    if (!key) {
      showToast("Please enter a valid API key.", true);
      return;
    }

    showLoader("Saving API key...", "Storing personal credentials securely in Google Apps Script");

    google.script.run
      .withSuccessHandler(res => {
        hideLoader();
        appState.hasApiKey = true;
        if (res && res.apiKeyStatus) {
          appState.apiKeyStatus = res.apiKeyStatus;
        } else {
          appState.apiKeyStatus = { hasPersonalKey: true, hasSharedKey: false, activeKeyType: 'personal' };
        }
        updateApiBadge();
        showToast("Personal Gemini API key saved securely!");
      })
      .withFailureHandler(err => {
        hideLoader();
        showToast("Failed to save API Key: " + err.message, true);
      })
      .saveApiKey(key);
  }

  /**
   * Delete API Key from PropertiesService
   */
  function handleDeleteApiKey() {
    showLoader("Clearing personal API key...", "Removing personal credentials from Google Apps Script");

    google.script.run
      .withSuccessHandler(res => {
        hideLoader();
        if (res && res.apiKeyStatus) {
          appState.apiKeyStatus = res.apiKeyStatus;
          appState.hasApiKey = res.apiKeyStatus.activeKeyType !== 'none';
        } else {
          appState.hasApiKey = false;
          appState.apiKeyStatus = { hasPersonalKey: false, hasSharedKey: false, activeKeyType: 'none' };
        }
        updateApiBadge();
        if (appState.apiKeyStatus.activeKeyType === 'shared') {
          showToast("Personal key cleared. Reverted to shared starter key.");
        } else {
          showToast("Personal Gemini API key cleared.");
        }
      })
      .withFailureHandler(err => {
        hideLoader();
        showToast("Failed to delete API Key: " + err.message, true);
      })
      .deleteApiKey();
  }

  /**
   * Generate Meal Plan using Gemini API
   */
  function handleGenerateMealPlan() {
    const reusedList = Array.from(appState.reusedRecipes);
    const count = parseInt(els.mealCountInput.value, 10) || 4;
    const planPreferences = els.planPreferencesInput ? els.planPreferencesInput.value.trim() : "";
    const selectedTagsList = Array.from(appState.selectedTags);
    const lockedList = Array.from(appState.lockedIndices);
    const pantryList = appState.pantryIngredients || [];

    // If all recipes are locked, notify user
    if (appState.db.mealPlan && Array.isArray(appState.db.mealPlan.recipes) && appState.db.mealPlan.recipes.length > 0) {
      const validLocked = lockedList.filter(i => i < appState.db.mealPlan.recipes.length && i < count);
      if (validLocked.length >= count) {
        showToast("All recipes are currently locked! Unlock a recipe to regenerate.", true);
        return;
      }
    }

    if (reusedList.length + lockedList.length < count && !appState.hasApiKey) {
      if (appState.authenticated) {
        showToast("Please configure an API Key in Settings first.", true);
        switchView('settings');
      } else {
        showToast("Gemini API key is not configured.", true);
      }
      return;
    }

    const usingShared = appState.apiKeyStatus && appState.apiKeyStatus.activeKeyType === 'shared';
    let subtext = "";
    if (lockedList.length > 0 || reusedList.length > 0) {
      const keptCount = Math.min(count, lockedList.length + reusedList.length);
      const neededNew = Math.max(0, count - keptCount);
      subtext = `Keeping ${keptCount} locked/reused dishes + generating ${neededNew} new dishes (scaling for ${els.prefDiners.value || 4} diners).`;
    } else {
      subtext = usingShared
        ? `Generating ${count} dinner recipes using shared starter key. Scaling for ${els.prefDiners.value || 4} diners (10-15s).`
        : `Generating ${count} dinner recipes. Scaling ingredients for ${els.prefDiners.value || 4} diners (10-15s).`;
    }

    showLoader("Preparing Meal Plan...", subtext);

    google.script.run
      .withSuccessHandler(res => {
        hideLoader();
        appState.db = res.db;
        appState.reusedRecipes.clear();
        if (res.db && res.db.mealPlan && Array.isArray(res.db.mealPlan.lockedIndices)) {
          appState.lockedIndices = new Set(res.db.mealPlan.lockedIndices);
        }
        updateReuseBanners();
        renderMealPlan();
        showToast("Meal plan generated successfully!");
      })
      .withFailureHandler(err => {
        hideLoader();
        showToast("Generation failed: " + err.message, true);
      })
      .generateMealPlanServer(count, planPreferences, reusedList, selectedTagsList, lockedList, pantryList);
  }

  /**
   * Calculate the next upcoming Sunday and increment daily offsets.
   */
  function getNextSundayDateString(offsetDays = 0) {
    const d = new Date();
    const day = d.getDay();
    // Calculate steps to Sunday. If today is Sunday (0), next Sunday is in 7 days
    let steps = 7 - day;
    if (steps === 0) steps = 7;

    d.setDate(d.getDate() + steps + offsetDays);

    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }

  /**
   * Renders the Meal Plan interface based on current DB state
   */
  function renderMealPlan() {
    const plan = appState.db.mealPlan;

    if (!plan) {
      els.plannerContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🍽️</div>
        <h3>No Meal Plan Generated Yet</h3>
        <p>Choose the number of meals to generate above and click Generate Dinner Plan to begin.</p>
      </div>
    `;
      return;
    }

    cacheActivePlanLocally(plan);

    // Reset selection set
    appState.selectedRecipes.clear();

    // Header HTML
    let html = `
    <div class="meal-plan-header">
      <div>
        <div class="meal-plan-title">Active Weekly Plan</div>
        <div class="meal-plan-metadata">Generated at: ${new Date(plan.generatedAt).toLocaleString()}</div>
      </div>
      <div>
  `;

    if (appState.authenticated) {
      if (!plan.approved) {
        html += `<button class="btn btn-gold" onclick="handleExecutePlan()"><i class="brand-icon" style="font-size:16px;">✓</i> Execute Approved Plan</button>`;
      } else {
        html += `<span class="api-badge active" style="font-size: 13px; padding: 8px 16px;">✓ Fully Approved & Executed</span>`;
      }
    }

    html += `
      </div>
    </div>
  `;

    // If plan is approved and fully executed, show link to Google Calendar
    if (plan.approved && plan.executionResult) {
      html += `
      <div class="success-box">
        <h4 class="success-title">Meal plan scheduled on Google Calendar!</h4>
        <p class="success-desc">Individual recipe instructions and your categorized grocery list have been added directly to your Default Google Calendar events.</p>
        <div class="success-links">
          <a href="https://calendar.google.com" target="_blank" class="doc-link">📅 Open Google Calendar</a>
        </div>
      </div>
    `;
    }

    // Render Recipe Cards Grid
    html += `<div class="recipe-grid">`;

    plan.recipes.forEach((recipe, idx) => {
      // Add to initial selection set
      appState.selectedRecipes.add(recipe.name);

      // Default scheduled date logic
      let defaultDate = getNextSundayDateString(idx);

      // Find if date was already saved in execution results
      if (plan.approved && plan.executionResult && plan.executionResult.recipeDocs) {
        const match = plan.executionResult.recipeDocs.find(d => d.name === recipe.name);
        if (match) {
          defaultDate = match.date;
        }
      }

      // Compute total time badge
      const totalTimeBadge = calculateTotalTime(recipe.prepTime, recipe.cookTime);

      // Favorite status
      const ratingInfo = (appState.historyData && appState.historyData.ratings && appState.historyData.ratings[recipe.name]) || (appState.db.recipeRatings && appState.db.recipeRatings[recipe.name]);
      const isFav = ratingInfo ? (ratingInfo.isFavorite === true || ratingInfo.rating > 0) : false;

      // Lock status
      const isLocked = appState.lockedIndices.has(idx);

      // Match on-hand pantry ingredients (MPA-12)
      const activePantryList = (plan.pantryIngredients && Array.isArray(plan.pantryIngredients) && plan.pantryIngredients.length > 0)
        ? plan.pantryIngredients
        : (appState.pantryIngredients || []);
      const matchedPantryItems = getMatchedPantryItemsForRecipe(recipe, activePantryList);
      const hasPantryMatches = matchedPantryItems.length > 0;

      // Build recipe details list
      const ingredientsList = recipe.ingredients.map(ing => {
        const isPantry = isPantryItemMatch(ing.name, activePantryList);
        const badgeHtml = isPantry ? ` <span class="pantry-item-badge">🥕 Pantry Item</span>` : '';
        return `<li>${escapeHtml(ing.amount)} ${escapeHtml(ing.unit)} ${escapeHtml(ing.name)}${badgeHtml}</li>`;
      }).join('');
      const instructionsList = recipe.instructions.map(step => `<li>${escapeHtml(step)}</li>`).join('');

      html += `
      <div class="recipe-card approved-card ${isLocked ? 'locked' : ''}" id="recipe-${idx}" onclick="handleCardClick(event, ${idx})">
        <div class="recipe-card-header">
          <div class="recipe-title-group">
            <div class="recipe-title">${escapeHtml(recipe.name)}</div>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-top:2px;">
              <div class="total-time-badge">${totalTimeBadge}</div>
              ${hasPantryMatches ? `
                <div class="recipe-pantry-badge" title="Uses on-hand ingredients: ${escapeHtml(matchedPantryItems.join(', '))}">
                  🥕 Uses: ${escapeHtml(matchedPantryItems.join(', '))}
                </div>
              ` : ''}
              <button type="button" class="favorite-btn ${isFav ? 'active' : ''}" 
                onclick="handleToggleFavorite(event, '${escapeJSString(recipe.name)}', ${idx})"
                title="${isFav ? 'Family Favorite' : 'Star / Bookmark Recipe'}">
                <span class="star-icon">${isFav ? '★' : '☆'}</span>
                <span>${isFav ? 'Favorite' : 'Star'}</span>
              </button>
              ${!plan.approved ? `
                <button type="button" class="btn-card-lock ${isLocked ? 'active' : ''}"
                  onclick="handleToggleRecipeLock(event, ${idx})"
                  title="${isLocked ? 'Unlock recipe' : 'Lock recipe to keep during plan regeneration'}">
                  <span class="lock-icon">${isLocked ? '🔒' : '🔓'}</span>
                  <span>${isLocked ? 'Locked' : 'Lock'}</span>
                </button>
                <button type="button" class="btn-card-swap ${isLocked ? 'disabled' : ''}"
                  ${isLocked ? 'disabled' : ''}
                  onclick="handleRerollSingleRecipe(event, ${idx})"
                  title="${isLocked ? 'Unlock recipe to swap' : 'Swap / Reroll this individual recipe'}">
                  <span>🔄 Swap</span>
                </button>
                <button type="button" class="btn-card-remove" 
                  ${isLocked ? 'disabled style="opacity:0.4; cursor:not-allowed;"' : ''}
                  onclick="${isLocked ? 'event.stopPropagation()' : `handleRemoveRecipeFromPlan(event, ${idx})`}" 
                  title="${isLocked ? 'Unlock recipe to remove' : 'Remove from this week\'s plan'}">
                  <span>✕ Remove</span>
                </button>
              ` : ''}
            </div>
          </div>
          <div class="recipe-checkbox-hitbox" title="Toggle plan inclusion" onclick="toggleRecipeSelection(event, ${idx}, '${escapeJSString(recipe.name)}')">
            <div class="recipe-checkbox" id="check-${idx}"></div>
          </div>
        </div>
        
        <div class="recipe-desc mobile-teaser">${escapeHtml(recipe.description)}</div>

        <div class="card-expand-indicator">
          <span>Details & Schedule</span>
          <i class="chevron">▼</i>
        </div>
        
        <div class="recipe-card-collapsible">
          <div class="recipe-date-container" onclick="event.stopPropagation()">
            <span class="recipe-date-label">Schedule Prep:</span>
            ${plan.approved
          ? `<span style="font-size: 13px; font-weight:600; color:var(--accent-secondary);">${defaultDate}</span>`
          : `<input type="date" class="recipe-date-input" id="date-${idx}" value="${defaultDate}">`
        }
          </div>
          
          <div class="recipe-meta-row">
            <div class="recipe-meta-item">⏱️ Prep: ${escapeHtml(recipe.prepTime)}</div>
            <div class="recipe-meta-item">🔥 Cook: ${escapeHtml(recipe.cookTime)}</div>
          </div>
          
          <div class="recipe-accordion" onclick="event.stopPropagation()">
            <button type="button" class="recipe-accordion-btn" onclick="toggleDetails(${idx})">
              <span>📋 View Ingredients & Steps</span>
            </button>
            
            <div class="recipe-details" id="details-${idx}">
              <div class="detail-section">
                <div class="detail-heading">Ingredients</div>
                <ul class="detail-list">
                  ${ingredientsList}
                </ul>
              </div>
              <div class="detail-section">
                <div class="detail-heading">Instructions</div>
                <ul class="detail-list">
                  ${instructionsList}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    });

    html += `</div>`;

    // Re-generate button for quick updates
    if (!plan.approved) {
      html += `
      <div style="display:flex; justify-content:center; margin-top:16px;">
        <button class="btn btn-secondary" onclick="handleGenerateMealPlan()"><i class="brand-icon" style="font-size:14px; color:var(--accent-primary);">✦</i> Regenerate Entire Plan</button>
      </div>
    `;
    }

    els.plannerContainer.innerHTML = html;
  }

  /**
   * Handle removing an individual recipe from unapproved active meal plan
   */
  function handleRemoveRecipeFromPlan(event, idx) {
    if (event) event.stopPropagation();
    if (!appState.db.mealPlan || !appState.db.mealPlan.recipes) return;

    const removedRecipe = appState.db.mealPlan.recipes[idx];
    appState.db.mealPlan.recipes.splice(idx, 1);

    // Shift locked indices accordingly
    const updatedLocked = new Set();
    appState.lockedIndices.forEach(lockedIdx => {
      if (lockedIdx < idx) {
        updatedLocked.add(lockedIdx);
      } else if (lockedIdx > idx) {
        updatedLocked.add(lockedIdx - 1);
      }
    });
    appState.lockedIndices = updatedLocked;
    if (appState.db.mealPlan) {
      appState.db.mealPlan.lockedIndices = Array.from(updatedLocked);
    }

    renderMealPlan();
    showToast(removedRecipe ? `Removed "${removedRecipe.name}" from plan.` : "Removed meal from plan.");

    // Persist updated plan to server
    google.script.run
      .withFailureHandler(err => console.error("Failed to sync plan update: " + err.message))
      .saveActiveMealPlanServer(appState.db.mealPlan.recipes);
  }

  /**
   * Handle card expansion on click/tap
   */
  function handleCardClick(event, idx) {
    const card = document.getElementById(`recipe-${idx}`);
    if (!card) return;
    card.classList.toggle('expanded');
  }

  /**
   * Handle individual card selection toggles
   */
  function toggleRecipeSelection(event, idx, recipeName) {
    if (event) {
      event.stopPropagation();
    }
    const plan = appState.db.mealPlan;
    if (plan && plan.approved) return; // Disallow toggle if already approved

    const card = document.getElementById(`recipe-${idx}`);
    if (!card) return;

    if (appState.selectedRecipes.has(recipeName)) {
      appState.selectedRecipes.delete(recipeName);
      card.classList.remove('approved-card');
      card.classList.add('deselected-card');
    } else {
      appState.selectedRecipes.add(recipeName);
      card.classList.remove('deselected-card');
      card.classList.add('approved-card');
    }
  }

  /**
   * Toggle details accordion inside card
   */
  function toggleDetails(idx) {
    const details = document.getElementById(`details-${idx}`);
    const btn = details.previousElementSibling;

    if (details.classList.contains('open')) {
      details.classList.remove('open');
      btn.innerHTML = "<span>📋 View Ingredients & Steps</span>";
    } else {
      details.classList.add('open');
      btn.innerHTML = "<span>❌ Hide Ingredients & Steps</span>";
    }
  }

  /**
   * Executes approved meal plan
   */
  function handleExecutePlan() {
    const plan = appState.db.mealPlan;
    if (!plan) return;

    // Gather approved recipe name and date mappings
    const approvedList = [];
    plan.recipes.forEach((recipe, idx) => {
      if (appState.selectedRecipes.has(recipe.name)) {
        const dateEl = document.getElementById(`date-${idx}`);
        const dateVal = dateEl ? dateEl.value : getNextSundayDateString(idx);
        approvedList.push({
          name: recipe.name,
          date: dateVal
        });
      }
    });

    if (approvedList.length === 0) {
      showToast("Please approve at least one recipe before executing.", true);
      return;
    }

    showLoader("Executing Workflow...", "Generating Google Docs for each recipe, scheduling calendar events, and compiling consolidated shopping list inside the folders in your Google Drive.");

    google.script.run
      .withSuccessHandler(res => {
        hideLoader();
        appState.db = res.db;
        renderMealPlan();
        showToast("Workspace pipeline completed successfully!");
      })
      .withFailureHandler(err => {
        hideLoader();
        showToast("Execution failed: " + err.message, true);
      })
      .approveMealPlanServer(approvedList);
  }

  /**
   * Loading Screen Helpers
   */
  function showLoader(title, subtext) {
    document.getElementById('loading-title').innerText = title;
    document.getElementById('loading-subtext').innerText = subtext;
    els.loader.style.display = 'flex';

    // Hide active views during loader
    els.views.forEach(v => v.style.display = 'none');
  }

  function hideLoader() {
    els.loader.style.display = 'none';
    // Restore views
    els.views.forEach(v => v.style.display = '');
  }

  /**
   * Toast Notifications
   */
  let toastTimeout;
  function showToast(message, isError = false) {
    clearTimeout(toastTimeout);

    els.toast.innerHTML = isError
      ? `⚠️ <span style="flex-grow:1;">${message}</span>`
      : `✅ <span style="flex-grow:1;">${message}</span>`;

    if (isError) {
      els.toast.classList.add('toast-error');
      els.toast.classList.remove('toast-success');
    } else {
      els.toast.classList.remove('toast-error');
      els.toast.classList.add('toast-success');
    }

    els.toast.classList.add('show');

    toastTimeout = setTimeout(() => {
      els.toast.classList.remove('show');
    }, 4000);
  }

  /**
   * Switch History sub-tab ('recent' | 'favorites')
   */
  function switchHistoryTab(tabId) {
    appState.historyTab = tabId;
    const isRecent = tabId === 'recent';

    if (els.subtabRecent) els.subtabRecent.classList.toggle('active', isRecent);
    if (els.subtabFavorites) els.subtabFavorites.classList.toggle('active', !isRecent);

    if (els.historyDesc) {
      els.historyDesc.textContent = isRecent
        ? "Review the 25 most recently scheduled recipes from your Google Drive. Rate your favorites and check boxes to re-use recipes in your next plan."
        : "Your 25 highest-rated favorite recipes, sorted by rating and recency. Check boxes to re-use recipes in your next plan.";
    }

    renderHistoryList();
  }

  /**
   * Toggle a recipe selection for ephemeral reuse
   */
  function toggleReuseRecipe(recipeName) {
    if (appState.reusedRecipes.has(recipeName)) {
      appState.reusedRecipes.delete(recipeName);
    } else {
      appState.reusedRecipes.add(recipeName);
    }
    updateReuseBanners();
    renderHistoryList();
  }

  /**
   * Clear all staged reused recipes
   */
  function clearReusedRecipes() {
    appState.reusedRecipes.clear();
    updateReuseBanners();
    renderHistoryList();
    showToast("Cleared re-used recipe selections.");
  }

  /**
   * Update Staged Re-use Banners in History and Planner views
   */
  function updateReuseBanners() {
    const count = appState.reusedRecipes.size;

    // History Banner
    if (els.historyReuseBanner) {
      if (count > 0) {
        els.historyReuseBanner.style.display = 'flex';
        if (els.reuseBannerText) {
          els.reuseBannerText.innerHTML = `<strong>${count} recipe${count > 1 ? 's' : ''}</strong> selected to re-use in your next plan`;
        }
      } else {
        els.historyReuseBanner.style.display = 'none';
      }
    }

    // Planner Notice
    if (els.plannerReuseNotice) {
      if (count > 0) {
        els.plannerReuseNotice.style.display = 'flex';
        const pillsHtml = Array.from(appState.reusedRecipes).map(name => `
          <span class="planner-reuse-pill">
            <span>✨ ${escapeHtml(name)}</span>
            <button type="button" onclick="toggleReuseRecipe('${escapeJSString(name)}')" style="background:none;border:none;color:var(--text-muted);cursor:pointer;padding:0 2px;font-size:11px;" title="Remove">✕</button>
          </span>
        `).join('');

        els.plannerReuseNotice.innerHTML = `
          <div style="flex:1;">
            <div style="font-weight:600; color:var(--accent-primary); margin-bottom:2px;">✦ ${count} Past Recipe${count > 1 ? 's' : ''} Staged for Re-use</div>
            <div class="planner-reuse-pills">${pillsHtml}</div>
          </div>
          <button type="button" class="btn btn-secondary btn-sm" onclick="clearReusedRecipes()" style="padding:4px 10px; font-size:11px; height:auto;">Clear All</button>
        `;
      } else {
        els.plannerReuseNotice.style.display = 'none';
        els.plannerReuseNotice.innerHTML = '';
      }
    }
  }

  /**
   * Handle single-star favorite toggle on a recipe
   */
  function handleToggleFavorite(event, recipeName, recipeObjOrIdx) {
    if (event) event.stopPropagation();

    let recipeObj = null;
    if (typeof recipeObjOrIdx === 'object' && recipeObjOrIdx !== null) {
      recipeObj = recipeObjOrIdx;
    } else if (typeof recipeObjOrIdx === 'number') {
      if (appState.db.mealPlan && Array.isArray(appState.db.mealPlan.recipes)) {
        recipeObj = appState.db.mealPlan.recipes[recipeObjOrIdx];
      }
    }
    if (!recipeObj) {
      if (appState.db.mealPlan && Array.isArray(appState.db.mealPlan.recipes)) {
        recipeObj = appState.db.mealPlan.recipes.find(r => r && r.name === recipeName);
      }
      if (!recipeObj && appState.db.recipeLibrary && appState.db.recipeLibrary[recipeName]) {
        recipeObj = appState.db.recipeLibrary[recipeName];
      }
    }

    // Determine current favorite status
    const currentInfo = (appState.historyData.ratings && appState.historyData.ratings[recipeName]) || (appState.db.recipeRatings && appState.db.recipeRatings[recipeName]);
    const currentlyFav = currentInfo ? (currentInfo.isFavorite === true || currentInfo.rating > 0) : false;
    const newIsFav = !currentlyFav;

    // Optimistically update local state
    if (!appState.historyData.ratings) appState.historyData.ratings = {};
    appState.historyData.ratings[recipeName] = {
      isFavorite: newIsFav,
      rating: newIsFav ? 5 : 0,
      favoritedAt: new Date().toISOString()
    };
    if (!appState.db.recipeRatings) appState.db.recipeRatings = {};
    appState.db.recipeRatings[recipeName] = appState.historyData.ratings[recipeName];

    // Cache recipe into library if object resolved
    if (recipeObj && typeof recipeObj === 'object') {
      if (!appState.db.recipeLibrary) appState.db.recipeLibrary = {};
      if (!appState.historyData.library) appState.historyData.library = {};
      appState.db.recipeLibrary[recipeName] = recipeObj;
      appState.historyData.library[recipeName] = recipeObj;
    }

    // Update items in history array
    appState.historyData.history.forEach(item => {
      if (item.name === recipeName) {
        item.isFavorite = newIsFav;
        item.rating = newIsFav ? 5 : 0;
      }
    });

    // Re-filter favorites array
    const favSet = new Map();
    appState.historyData.history.forEach(item => {
      if (item.isFavorite === true || item.rating > 0) favSet.set(item.name, item);
    });
    appState.historyData.favorites = Array.from(favSet.values()).sort((a, b) => {
      if (b.rating !== a.rating) return b.rating - a.rating;
      if (b.scheduledTime !== a.scheduledTime) return b.scheduledTime - a.scheduledTime;
      return (b.createdTime || 0) - (a.createdTime || 0);
    }).slice(0, 50);

    // Update subtab badges
    if (els.badgeRecentCount) els.badgeRecentCount.textContent = appState.historyData.history.length;
    if (els.badgeFavoritesCount) els.badgeFavoritesCount.textContent = appState.historyData.favorites.length;

    // Re-render views as needed
    if (els.historyContainer && appState.currentView === 'history') {
      renderHistoryList();
    }
    if (appState.currentView === 'planner') {
      renderMealPlan();
    }

    if (newIsFav) {
      showToast(`⭐ Added "${recipeName}" to Family Favorites!`);
    } else {
      showToast(`Removed "${recipeName}" from Family Favorites.`);
    }

    // Call server to persist favorite status in Drive DB
    google.script.run
      .withSuccessHandler(res => {
        if (res && res.recipeRatings) {
          appState.historyData.ratings = res.recipeRatings;
          appState.db.recipeRatings = res.recipeRatings;
        }
        if (res && res.recipeLibrary) {
          appState.historyData.library = res.recipeLibrary;
          appState.db.recipeLibrary = res.recipeLibrary;
        }
      })
      .withFailureHandler(err => {
        showToast("Failed to save favorite: " + err.message, true);
      })
      .toggleFavoriteRecipeServer(recipeName, newIsFav, recipeObj);
  }

  /**
   * Helper function to render a single-star favorite button (backward-compatible alias)
   */
  function renderStarRating(recipeName, rating = 0) {
    const isFav = rating > 0;
    return `
      <button type="button" class="favorite-btn ${isFav ? 'active' : ''}" 
        onclick="handleToggleFavorite(event, '${escapeJSString(recipeName)}')"
        title="${isFav ? 'Family Favorite' : 'Star / Bookmark Recipe'}">
        <span class="star-icon">${isFav ? '★' : '☆'}</span>
        <span>${isFav ? 'Favorite' : 'Star'}</span>
      </button>
    `;
  }

  /**
   * Backward-compatible rating setter
   */
  function handleSetRating(event, recipeName, selectedScore) {
    handleToggleFavorite(event, recipeName);
  }

  /**
   * Quick-add a recipe from History or Favorites directly into the active meal plan (MPA-15)
   */
  function handleQuickAddToPlan(event, recipeName) {
    if (event) event.stopPropagation();

    // Look up structured recipe from recipeLibrary or historyData
    let recipe = (appState.db.recipeLibrary && appState.db.recipeLibrary[recipeName]) ||
                 (appState.historyData.library && appState.historyData.library[recipeName]);

    if (!recipe) {
      const histItem = (appState.historyData.history || []).find(h => h.name === recipeName) ||
                       (appState.historyData.favorites || []).find(f => f.name === recipeName);
      if (histItem) {
        recipe = {
          name: histItem.name,
          description: histItem.description || "Favorite recipe from history.",
          prepTime: histItem.prepTime || "20 mins",
          cookTime: histItem.cookTime || "30 mins",
          ingredients: [],
          instructions: [],
          docUrl: histItem.docUrl || histItem.url || "",
          docId: histItem.fileId || ""
        };
      }
    }

    if (!recipe) {
      showToast(`Cannot find details for "${recipeName}".`, true);
      return;
    }

    if (!appState.db.mealPlan) {
      appState.db.mealPlan = {
        recipes: [],
        approved: false,
        generatedAt: new Date().toISOString(),
        selectedTags: [],
        pantryIngredients: [],
        lockedIndices: []
      };
    }

    // Check if recipe already exists in active plan
    const alreadyInPlan = appState.db.mealPlan.recipes.some(r => r.name === recipe.name);
    if (alreadyInPlan) {
      showToast(`"${recipe.name}" is already in your active weekly plan.`);
      switchView('planner');
      return;
    }

    // Clone recipe to avoid reference mutations
    const clonedRecipe = JSON.parse(JSON.stringify(recipe));
    clonedRecipe.isReused = true;

    // Add to active recipes
    appState.db.mealPlan.recipes.push(clonedRecipe);

    // If plan was previously approved, unapprove it to prompt re-execution
    appState.db.mealPlan.approved = false;

    // Persist updated plan to server
    google.script.run
      .withSuccessHandler(res => {
        showToast(`✓ Added "${recipe.name}" to your active meal plan!`);
        switchView('planner');
      })
      .withFailureHandler(err => {
        showToast("Error updating meal plan: " + err.message, true);
      })
      .saveActiveMealPlanServer(appState.db.mealPlan.recipes);
  }

  /**
   * Fetch recipe history and favorites from server
   */
  function loadHistoryData() {
    els.historyContainer.innerHTML = `
      <div style="display:flex; justify-content:center; align-items:center; padding: 32px;">
        <div class="loader" style="width:32px; height:32px; border-width:3px; margin-bottom:0; margin-right: 12px;"></div>
        <span style="font-size:14px; color:var(--text-secondary);">Retrieving recipe history...</span>
      </div>
    `;

    google.script.run
      .withSuccessHandler(onHistoryLoaded)
      .withFailureHandler(err => {
        els.historyContainer.innerHTML = `
          <div style="color:var(--error); padding: 16px; font-size:14px; background:rgba(239,68,68,0.05); border: 1px solid rgba(239,68,68,0.15); border-radius:8px;">
            ⚠️ Failed to load recipe history: ${err.message}
          </div>
        `;
      })
      .getRecipeHistory();
  }

  /**
   * Render history list when loaded from server
   */
  function onHistoryLoaded(data) {
    if (Array.isArray(data)) {
      appState.historyData = { history: data, favorites: [], ratings: {}, library: {} };
    } else if (data) {
      appState.historyData = {
        history: data.history || [],
        favorites: data.favorites || [],
        ratings: data.ratings || {},
        library: data.library || {}
      };
      if (data.library) {
        appState.db.recipeLibrary = Object.assign({}, appState.db.recipeLibrary, data.library);
      }
      if (data.ratings) {
        appState.db.recipeRatings = Object.assign({}, appState.db.recipeRatings, data.ratings);
      }
    }

    // Update subtab badges
    if (els.badgeRecentCount) els.badgeRecentCount.textContent = appState.historyData.history.length;
    if (els.badgeFavoritesCount) els.badgeFavoritesCount.textContent = appState.historyData.favorites.length;

    updateReuseBanners();
    renderHistoryList();
  }

  /**
   * Render history list based on current active tab
   */
  function renderHistoryList() {
    const isRecent = appState.historyTab === 'recent';
    const items = isRecent ? appState.historyData.history : appState.historyData.favorites;

    if (!items || items.length === 0) {
      if (isRecent) {
        els.historyContainer.innerHTML = `
          <div class="empty-state" style="border-style: solid; padding: 32px 16px;">
            <div class="empty-state-icon" style="font-size:32px;">📜</div>
            <h3>No Recipe Docs Found</h3>
            <p>Once you generate and execute a meal plan, approved recipes will be saved in your Google Drive and displayed here.</p>
          </div>
        `;
      } else {
        els.historyContainer.innerHTML = `
          <div class="empty-state" style="border-style: solid; padding: 32px 16px;">
            <div class="empty-state-icon" style="font-size:32px;">⭐</div>
            <h3>No Family Favorites Yet</h3>
            <p>Click the <strong>⭐ Star</strong> button on any recipe card in your Planner or Recipe History to save your staples here!</p>
          </div>
        `;
      }
      return;
    }

    let html = `<div class="history-list">`;

    items.forEach(item => {
      const isReused = appState.reusedRecipes.has(item.name);
      const ratingInfo = (appState.historyData.ratings && appState.historyData.ratings[item.name]) || (appState.db.recipeRatings && appState.db.recipeRatings[item.name]);
      const isFav = ratingInfo ? (ratingInfo.isFavorite === true || ratingInfo.rating > 0) : (item.isFavorite || item.rating > 0);

      html += `
        <div class="history-item ${isReused ? 'staged-for-reuse' : ''}">
          <div class="history-item-left">
            <label class="history-checkbox-wrap" title="Select to re-use in next batch generation">
              <input type="checkbox" class="history-checkbox" 
                ${isReused ? 'checked' : ''} 
                onchange="toggleReuseRecipe('${escapeJSString(item.name)}')">
            </label>
            <span class="history-item-date">${escapeHtml(item.date)}</span>
            <span class="history-item-name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span>
          </div>
          <div class="history-item-right">
            <button type="button" class="favorite-btn ${isFav ? 'active' : ''}" 
              onclick="handleToggleFavorite(event, '${escapeJSString(item.name)}')"
              title="${isFav ? 'Remove from Family Favorites' : 'Add to Family Favorites'}">
              <span class="star-icon">${isFav ? '★' : '☆'}</span>
              <span>${isFav ? 'Favorite' : 'Star'}</span>
            </button>
            <button type="button" class="btn-quick-add" 
              onclick="handleQuickAddToPlan(event, '${escapeJSString(item.name)}')"
              title="Insert recipe into active weekly meal plan">
              <span>➕ Add to Plan</span>
            </button>
            ${(item.docUrl || item.url)
              ? `<a href="${escapeHtml(item.docUrl || item.url)}" target="_blank" class="doc-link" title="Open Google Doc">📄 Open Doc</a>`
              : `<button type="button" class="doc-link doc-link-create" onclick="handleCreateRecipeDoc(event, '${escapeJSString(item.name)}')" title="Generate a Google Doc for this recipe">📄 Create Recipe</button>`
            }
          </div>
        </div>
      `;
    });

    html += `</div>`;
    els.historyContainer.innerHTML = html;
  }

  /**
   * On-demand generation of Google Doc for a recipe from History / Favorites
   */
  function handleCreateRecipeDoc(event, recipeName) {
    if (event) event.stopPropagation();
    const btn = event ? event.currentTarget : null;
    const originalHtml = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span class="loading-spinner-inline"></span> Creating...`;
    }

    showToast(`Creating Google Doc for "${recipeName}"...`);

    google.script.run
      .withSuccessHandler(function (res) {
        if (res && res.success && res.docUrl) {
          showToast(`✓ Google Doc created for "${recipeName}"!`);
          if (appState.historyData && appState.historyData.library && appState.historyData.library[recipeName]) {
            appState.historyData.library[recipeName].docUrl = res.docUrl;
            appState.historyData.library[recipeName].docId = res.docId;
          }
          window.open(res.docUrl, '_blank');
          renderHistoryList();
        } else {
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
          }
          showToast("Could not create recipe document.", true);
        }
      })
      .withFailureHandler(function (err) {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = originalHtml;
        }
        showToast("Error creating recipe document: " + err.message, true);
      })
      .createRecipeDocServer(recipeName);
  }

  /**
   * Displays an unobtrusive toast notification.
   */
  function showToast(message, isError = false, duration = 4000) {
    const toast = els.toast || document.getElementById('toast');
    if (!toast) return;
    const span = toast.querySelector('span') || toast;
    span.textContent = message;

    toast.className = 'toast show' + (isError ? ' toast-error' : ' toast-success');

    if (window._toastTimeout) {
      clearTimeout(window._toastTimeout);
    }
    window._toastTimeout = setTimeout(() => {
      toast.classList.remove('show');
    }, duration);
  }

  /**
   * Checks for query parameters on startup (such as OAuth redirects)
   */
  function checkUrlParams() {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('logged_in') === 'true') {
        showToast('✓ Successfully signed in with Google!', false, 4000);
        window.history.replaceState({}, document.title, window.location.pathname);
      } else if (urlParams.get('error')) {
        const err = urlParams.get('error');
        const details = urlParams.get('details');
        let msg = 'Authentication error: ' + err;
        if (err === 'oauth_failed') {
          msg = 'Google Sign-In failed. ' + (details ? details : 'Please restart the app server and try again.');
        } else if (err === 'oauth_denied') {
          msg = 'Google Sign-In was cancelled or access was denied.';
        }
        showToast(msg, true, 6000);
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    } catch (e) {
      console.warn('Could not parse URL params', e);
    }
  }

