/**
 * REST API Client for the Meal Planning Assistant.
 * Replaces google.script.run with standard fetch() requests to the Flask backend.
 * Provides both modern Promise-based methods and a drop-in google.script.run compatibility shim.
 */

const apiClient = {
  async _request(endpoint, method = "GET", body = null) {
    const options = {
      method,
      headers: {
        "Content-Type": "application/json",
      },
    };
    if (body !== null && method !== "GET") {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(endpoint, options);
      const data = await response.json();
      if (!response.ok || data.success === false) {
        throw new Error(data.error || `HTTP ${response.status}: Request failed`);
      }
      return data;
    } catch (err) {
      console.error(`API Error [${method} ${endpoint}]:`, err);
      throw err;
    }
  },

  loadAppData() {
    return this._request("/api/data");
  },

  savePreferences(preferences) {
    return this._request("/api/preferences", "POST", { preferences });
  },

  setSkipWelcomePreference(skip) {
    return this._request("/api/preferences/skip-welcome", "POST", { skip });
  },

  saveApiKey(apiKey) {
    return this._request("/api/settings/api-key", "POST", { apiKey });
  },

  deleteApiKey() {
    return this._request("/api/settings/api-key", "DELETE");
  },

  generateMealPlanServer(mealCount, planPreferences, reusedRecipeNames, selectedTags, lockedIndices, pantryIngredients) {
    return this._request("/api/meal-plan/generate", "POST", {
      mealCount,
      planPreferences,
      reusedRecipeNames,
      selectedTags,
      lockedIndices,
      pantryIngredients
    });
  },

  rerollSingleRecipeServer(targetIndex, existingRecipes, planPreferences, selectedTags, pantryIngredients) {
    return this._request("/api/meal-plan/reroll", "POST", {
      targetIndex,
      existingRecipes,
      planPreferences,
      selectedTags,
      pantryIngredients
    });
  },

  saveActiveMealPlanServer(recipesList) {
    return this._request("/api/meal-plan/active", "PUT", { recipes: recipesList });
  },

  approveMealPlanServer(approvedMealsWithDates) {
    return this._request("/api/meal-plan/approve", "POST", { approvedMealsWithDates });
  },

  createRecipeDocServer(recipeName) {
    return this._request("/api/recipes/create-doc", "POST", { recipeName });
  },

  getRecipeHistory() {
    return this._request("/api/recipes/history");
  },

  toggleFavoriteRecipeServer(recipeName, isFavorite, recipeObj) {
    return this._request("/api/recipes/favorite", "POST", {
      recipeName,
      isFavorite,
      recipeObj
    });
  },

  setRecipeRating(recipeName, rating) {
    return this._request("/api/recipes/rating", "POST", { recipeName, rating });
  },

  syncShoppingChecklistServer(checkedItems, customItems) {
    return this._request("/api/shopping/sync", "POST", { checkedItems, customItems });
  }
};

/**
 * Drop-in google.script.run compatibility shim.
 * Maps legacy .withSuccessHandler().withFailureHandler().functionName(...) to REST endpoints.
 */
class GasRunShim {
  constructor() {
    this._successHandler = () => {};
    this._failureHandler = (err) => console.error("GAS Shim Error:", err);
  }

  withSuccessHandler(fn) {
    this._successHandler = fn;
    return this;
  }

  withFailureHandler(fn) {
    this._failureHandler = fn;
    return this;
  }

  _execute(promise) {
    promise
      .then(res => this._successHandler(res))
      .catch(err => this._failureHandler(err));
  }

  loadAppData() {
    this._execute(apiClient.loadAppData());
  }

  savePreferences(prefs) {
    this._execute(apiClient.savePreferences(prefs));
  }

  setSkipWelcomePreference(skip) {
    this._execute(apiClient.setSkipWelcomePreference(skip));
  }

  saveApiKey(key) {
    this._execute(apiClient.saveApiKey(key));
  }

  deleteApiKey() {
    this._execute(apiClient.deleteApiKey());
  }

  generateMealPlanServer(mealCount, planPrefs, reusedNames, tags, lockedIndices, pantry) {
    this._execute(apiClient.generateMealPlanServer(mealCount, planPrefs, reusedNames, tags, lockedIndices, pantry));
  }

  rerollSingleRecipeServer(targetIndex, existing, planPrefs, tags, pantry) {
    this._execute(apiClient.rerollSingleRecipeServer(targetIndex, existing, planPrefs, tags, pantry));
  }

  saveActiveMealPlanServer(recipes) {
    this._execute(apiClient.saveActiveMealPlanServer(recipes));
  }

  approveMealPlanServer(approvedMeals) {
    this._execute(apiClient.approveMealPlanServer(approvedMeals));
  }

  createRecipeDocServer(recipeName) {
    this._execute(apiClient.createRecipeDocServer(recipeName));
  }

  getRecipeHistory() {
    this._execute(apiClient.getRecipeHistory());
  }

  toggleFavoriteRecipeServer(name, isFav, obj) {
    this._execute(apiClient.toggleFavoriteRecipeServer(name, isFav, obj));
  }

  setRecipeRating(name, rating) {
    this._execute(apiClient.setRecipeRating(name, rating));
  }

  syncShoppingChecklistServer(checked, custom) {
    this._execute(apiClient.syncShoppingChecklistServer(checked, custom));
  }
}

// Polyfill window.google.script.run
window.google = window.google || {};
window.google.script = window.google.script || {};
Object.defineProperty(window.google.script, "run", {
  get() {
    return new GasRunShim();
  }
});
