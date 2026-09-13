class TravelMapManager {
    constructor() {
        this.map = null;
        this.markers = [];
        this.allPlaces = [];
        this.filteredPlaces = [];
        this.cities = [];
        this.categories = [];
        this.currentCity = "darjeeling";
        this.currentCategory = "";
        this.currentSearch = "";
        this.activePlaceName = "";
        this.categoryColors = {
            accommodation: "#3498db",
            food_beverage: "#e74c3c",
            tourism_activity: "#2ecc71",
            shopping: "#f39c12",
            transportation: "#9b59b6",
            general: "#95a5a6"
        };
    }

    async init() {
        this.cacheDom();
        this.setupEventListeners();
        this.initMap();
        await this.loadInitialData();
    }

    cacheDom() {
        this.citySelector = document.getElementById("citySelector");
        this.categoryFilter = document.getElementById("sidebarCategoryFilter");
        this.placeSearch = document.getElementById("placeSearch");
        this.refreshPlacesBtn = document.getElementById("refreshPlacesBtn");
        this.clearFiltersBtn = document.getElementById("clearFiltersBtn");
        this.closeMapBtn = document.getElementById("closeMapBtn");
        this.placesList = document.getElementById("placesList");
        this.loadingOverlay = document.getElementById("loadingOverlay");
        this.pageTitle = document.getElementById("pageTitle");
        this.mapStatus = document.getElementById("mapStatus");
        this.mapCityBadge = document.getElementById("mapCityBadge");
        this.totalPlacesEl = document.getElementById("totalPlaces");
        this.avgRatingEl = document.getElementById("avgRating");
        this.activeCategoryLabelEl = document.getElementById("activeCategoryLabel");
        this.placesCountBadge = document.getElementById("placesCountBadge");
    }

    setupEventListeners() {
        if (this.citySelector) {
            this.citySelector.addEventListener("change", async (event) => {
                const nextCity = event.target.value || "darjeeling";
                this.currentCity = nextCity;
                await this.loadPlacesForCity(nextCity);
            });
        }

        if (this.categoryFilter) {
            this.categoryFilter.addEventListener("change", () => {
                this.currentCategory = this.categoryFilter.value;
                this.applyFilters();
            });
        }

        if (this.placeSearch) {
            this.placeSearch.addEventListener("input", () => {
                this.currentSearch = this.placeSearch.value.trim().toLowerCase();
                this.applyFilters();
            });
        }

        if (this.refreshPlacesBtn) {
            this.refreshPlacesBtn.addEventListener("click", async () => {
                await this.loadPlacesForCity(this.currentCity);
            });
        }

        if (this.clearFiltersBtn) {
            this.clearFiltersBtn.addEventListener("click", () => {
                this.currentCategory = "";
                this.currentSearch = "";
                if (this.categoryFilter) this.categoryFilter.value = "";
                if (this.placeSearch) this.placeSearch.value = "";
                this.applyFilters();
            });
        }

        if (this.closeMapBtn) {
            this.closeMapBtn.addEventListener("click", () => {
                if (window.history.length > 1) {
                    window.history.back();
                } else {
                    window.close();
                }
            });
        }
    }

    initMap() {
        this.map = L.map("map-embed", {
            zoomControl: true,
            scrollWheelZoom: true
        }).setView([26.7271, 88.3953], 9);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "© OpenStreetMap contributors",
            maxZoom: 18
        }).addTo(this.map);
    }

    async loadInitialData() {
        this.setLoading(true, "Loading destinations...");
        await Promise.all([this.loadCities(), this.loadCategories()]);

        if (this.citySelector && this.citySelector.options.length > 1) {
            this.citySelector.value = this.currentCity;
        }

        await this.loadPlacesForCity(this.currentCity);
    }

    async loadCities() {
        try {
            const response = await fetch("/api/scraped-cities");
            if (!response.ok) {
                throw new Error("Failed to fetch cities");
            }

            const data = await response.json();
            this.cities = Array.isArray(data.cities) ? data.cities : [];

            if (!this.citySelector) return;

            this.citySelector.innerHTML = '<option value="">Select city</option>';
            this.cities.forEach((city) => {
                const option = document.createElement("option");
                option.value = city.value;
                option.textContent = city.label;
                this.citySelector.appendChild(option);
            });
        } catch (error) {
            console.error("Error loading cities:", error);
            this.updateStatus("Could not load city list. Showing default map view.");
        }
    }

    async loadCategories() {
        try {
            const response = await fetch("/api/categories");
            if (!response.ok) {
                throw new Error("Failed to fetch categories");
            }

            const categories = await response.json();
            this.categories = Array.isArray(categories) ? categories : [];

            if (!this.categoryFilter) return;

            this.categoryFilter.innerHTML = '<option value="">All categories</option>';
            this.categories.forEach((category) => {
                const option = document.createElement("option");
                option.value = category.value;
                option.textContent = category.label;
                this.categoryFilter.appendChild(option);
            });
        } catch (error) {
            console.error("Error loading categories:", error);
        }
    }

    async loadPlacesForCity(city) {
        if (!city) {
            this.renderEmpty("Select a destination to explore places.");
            this.updateStats([]);
            this.clearMarkers();
            this.setLoading(false);
            return;
        }

        this.currentCity = city;
        this.activePlaceName = "";
        this.setLoading(true, "Loading places...");

        const places = await this.fetchPlaces(city);

        this.allPlaces = places;
        this.applyFilters();
        this.updateHeader(city);
        this.setLoading(false);
    }

    async fetchPlaces(city) {
        try {
            const response = await fetch(`/api/map-markers?city=${encodeURIComponent(city)}`);
            if (!response.ok) {
                throw new Error(`Failed to fetch places for ${city}`);
            }

            const places = await response.json();
            return Array.isArray(places) ? places : [];
        } catch (error) {
            console.error("Error loading places from API:", error);
            this.updateStatus("Places could not be loaded from the server right now.");
            return [];
        }
    }

    applyFilters() {
        const category = this.currentCategory;
        const searchTerm = this.currentSearch;

        this.filteredPlaces = this.allPlaces.filter((place) => {
            const placeCategory = String(place.category || "").toLowerCase();
            const haystack = [
                place.name,
                place.description,
                place.location,
                placeCategory,
                place.csvCategory,
                place.type,
                place.price
            ]
                .filter(Boolean)
                .join(" ")
                .toLowerCase();

            const matchesCategory = !category || placeCategory === category;
            const matchesSearch = !searchTerm || haystack.includes(searchTerm);

            return matchesCategory && matchesSearch;
        });

        this.renderPlacesList();
        this.updateStats(this.filteredPlaces);
        this.renderMarkers(this.filteredPlaces);
        this.updateFilterLabels();
    }

    renderPlacesList() {
        if (!this.placesList) return;

        if (this.filteredPlaces.length === 0) {
            const message = this.allPlaces.length === 0
                ? "No places are available for this destination yet. Try Refresh Places."
                : "No places match the current filters. Try clearing category or search.";
            this.renderEmpty(message);
            return;
        }

        this.placesList.innerHTML = this.filteredPlaces
            .map((place) => this.createPlaceListItem(place))
            .join("");

        this.placesList.querySelectorAll(".place-item").forEach((item, index) => {
            item.addEventListener("click", () => {
                this.focusOnPlace(this.filteredPlaces[index]);
                this.highlightPlaceCard(this.filteredPlaces[index].name);
            });
        });

        if (this.placesCountBadge) {
            this.placesCountBadge.textContent = `${this.filteredPlaces.length} place${this.filteredPlaces.length === 1 ? "" : "s"}`;
        }
    }

    renderEmpty(message) {
        if (!this.placesList) return;
        this.placesList.innerHTML = `<div class="map-empty">${message}</div>`;
        if (this.placesCountBadge) this.placesCountBadge.textContent = "0 places";
    }

    createPlaceListItem(place) {
        const safeName = this.escapeHtml(place.name || "Unknown place");
        const description = this.escapeHtml(place.description || place.location || "No description available");
        const categoryLabel = this.formatCategory(place.category);
        const locationLabel = this.escapeHtml(place.location || this.formatCity(this.currentCity));
        const color = (this.categoryColors[place.category] || this.categoryColors.general).replace("#", "");
        const initial = encodeURIComponent((place.name || "P").charAt(0).toUpperCase());
        const fallback = `https://via.placeholder.com/72x72/${color}/ffffff?text=${initial}`;

        const imageUrl = this.getPlaceImage(place) || fallback;

        return `
            <article class="place-item" data-place-name="${safeName}">
                <img
                    src="${imageUrl}"
                    alt="${safeName}"
                    onerror="this.onerror=null; this.src='${fallback}';"
                />
                <div class="place-item-content">
                    <h4>${safeName}</h4>
                    <p>${description}</p>
                    <div class="place-meta">
                        ${place.rating ? `<span class="place-rating">★ ${Number(place.rating).toFixed(1)}</span>` : ""}
                        ${categoryLabel ? `<span class="place-category">${this.escapeHtml(categoryLabel)}</span>` : ""}
                        ${place.price ? `<span class="place-location">💰 ${this.escapeHtml(place.price)}</span>` : ""}
                        <span class="place-location">${locationLabel}</span>
                    </div>
                </div>
            </article>
        `;
    }

    renderMarkers(places) {
        this.clearMarkers();

        if (!this.map || places.length === 0) {
            return;
        }

        const bounds = [];

        places.forEach((place) => {
            if (!place.coordinates || place.coordinates.latitude == null || place.coordinates.longitude == null) {
                return;
            }

            const { latitude, longitude } = place.coordinates;
            const color = this.categoryColors[place.category] || this.categoryColors.general;

            const marker = L.circleMarker([latitude, longitude], {
                radius: 8,
                fillColor: color,
                color: "#ffffff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.95
            });

            marker.bindPopup(this.createPopupContent(place), {
                className: "place-popup-wrapper"
            });

            marker.on("click", () => {
                this.highlightPlaceCard(place.name);
            });

            marker.addTo(this.map);
            this.markers.push(marker);
            bounds.push([latitude, longitude]);
        });

        if (bounds.length > 0) {
            this.map.fitBounds(bounds, { padding: [40, 40] });
        }
    }

    createPopupContent(place) {
        const name = this.escapeHtml(place.name || "Unknown place");
        const description = this.escapeHtml(place.description || place.location || "No description available");
        const meta = [];

        if (place.rating) {
            meta.push(`<span>★ ${Number(place.rating).toFixed(1)}</span>`);
        }

        if (place.category) {
            meta.push(`<span>${this.escapeHtml(this.formatCategory(place.category))}</span>`);
        }

        if (place.price) {
            meta.push(`<span>💰 ${this.escapeHtml(place.price)}</span>`);
        }

        if (place.location) {
            meta.push(`<span>${this.escapeHtml(place.location)}</span>`);
        }

        return `
            <div class="place-popup">
                <h4>${name}</h4>
                <p>${description}</p>
                <div class="place-popup__meta">${meta.join("")}</div>
            </div>
        `;
    }

    focusOnPlace(place) {
        if (!this.map || !place.coordinates) return;

        const { latitude, longitude } = place.coordinates;
        this.map.setView([latitude, longitude], 14, { animate: true });

        this.markers.forEach((marker) => {
            const markerLatLng = marker.getLatLng();
            if (
                Math.abs(markerLatLng.lat - latitude) < 0.0001 &&
                Math.abs(markerLatLng.lng - longitude) < 0.0001
            ) {
                marker.openPopup();
            }
        });
    }

    highlightPlaceCard(placeName) {
        this.activePlaceName = placeName || "";
        const items = this.placesList ? this.placesList.querySelectorAll(".place-item") : [];
        items.forEach((item) => {
            item.classList.toggle("is-active", item.dataset.placeName === this.activePlaceName);
        });
    }

    updateHeader(city) {
        const cityLabel = this.findCityLabel(city);
        if (this.pageTitle) {
            this.pageTitle.textContent = `${cityLabel} Places`;
        }
        if (this.mapCityBadge) {
            this.mapCityBadge.textContent = `📍 ${cityLabel}`;
        }
        this.updateStatus(`Showing places, hotels, food spots, and activities around ${cityLabel}.`);
    }

    updateStats(places) {
        const total = places.length;
        const ratings = places
            .map((place) => Number(place.rating))
            .filter((rating) => !Number.isNaN(rating) && rating > 0);

        const avgRating = ratings.length
            ? (ratings.reduce((sum, rating) => sum + rating, 0) / ratings.length).toFixed(1)
            : "0.0";

        if (this.totalPlacesEl) this.totalPlacesEl.textContent = String(total);
        if (this.avgRatingEl) this.avgRatingEl.textContent = avgRating;
    }

    updateFilterLabels() {
        if (this.activeCategoryLabelEl) {
            this.activeCategoryLabelEl.textContent = this.currentCategory
                ? this.formatCategory(this.currentCategory)
                : "All";
        }

        if (this.filteredPlaces.length > 0) {
            this.updateStatus(`Showing ${this.filteredPlaces.length} place${this.filteredPlaces.length === 1 ? "" : "s"} after filtering.`);
        } else if (this.allPlaces.length > 0) {
            this.updateStatus("No places match the active filters.");
        }
    }

    updateStatus(message) {
        if (this.mapStatus) {
            this.mapStatus.textContent = message;
        }
    }

    setLoading(isLoading, message = "Loading...") {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.toggle("is-visible", isLoading);
        }
        if (message) {
            this.updateStatus(message);
        }
    }

    clearMarkers() {
        this.markers.forEach((marker) => {
            if (this.map) {
                this.map.removeLayer(marker);
            }
        });
        this.markers = [];
    }

    findCityLabel(value) {
        const matched = this.cities.find((city) => city.value === value);
        return matched ? matched.label : this.formatCity(value);
    }

    formatCity(value) {
        return String(value || "")
            .replace(/[_-]+/g, " ")
            .replace(/\b\w/g, (char) => char.toUpperCase());
    }

    formatCategory(value) {
        return String(value || "")
            .replace(/_/g, " ")
            .replace(/\b\w/g, (char) => char.toUpperCase());
    }

    getPlaceImage(place) {
        if (Array.isArray(place.photos) && place.photos.length > 0 && place.photos[0]?.url) {
            return place.photos[0].url;
        }
        if (place.image) {
            return place.image;
        }
        return null;
    }

    escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = String(value ?? "");
        return div.innerHTML;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const mapManager = new TravelMapManager();
    mapManager.init();
});