const QUITOQUE_CARD_VERSION = "1.0.5";

const DEFAULT_CONFIG = {
  title: "Quitoque",
  display_mode: "detailed",
  show_empty_weeks: true,
  show_actions: true,
  recipes_collapsed: false,
  show_recipe_images: true,
  image_size: "medium",
  calendar_url: "",
  calendar_url_name: "Ouvrir calendrier",

  delivery_week_0: "sensor.quitoque_livraison_cette_semaine",
  delivery_week_1: "sensor.quitoque_livraison_dans_1_semaine",
  delivery_week_2: "sensor.quitoque_livraison_dans_2_semaines",
  delivery_week_3: "sensor.quitoque_livraison_dans_3_semaines",
  delivery_week_4: "sensor.quitoque_livraison_dans_4_semaines",

  recipe_count_week_0: "sensor.quitoque_nombre_de_recettes_cette_semaine",
  recipe_count_week_1: "sensor.quitoque_nombre_de_recettes_dans_1_semaine",
  recipe_count_week_2: "sensor.quitoque_nombre_de_recettes_dans_2_semaines",
  recipe_count_week_3: "sensor.quitoque_nombre_de_recettes_dans_3_semaines",
  recipe_count_week_4: "sensor.quitoque_nombre_de_recettes_dans_4_semaines",

  refresh_button: "button.quitoque_actualiser",
  calendar_button: "button.quitoque_ajouter_les_recettes_au_calendrier",
  pdf_button: "button.quitoque_generer_et_telecharger_les_pdf",
  config_entry_id: "",
};

const WEEK_KEYS = [0, 1, 2, 3, 4];

class QuitoqueCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._selectedWeek = null;
    this._busy = false;
    this._busyAction = null;
    this._recipesExpanded = null;
    this._lastHassSnapshot = null;
  }

  static getConfigElement() {
    return document.createElement("quitoque-card-editor");
  }

  static getStubConfig() {
    return { ...DEFAULT_CONFIG };
  }

  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...config };
    this._selectedWeek = null;
    this._recipesExpanded = this._config.recipes_collapsed !== true;
    this._lastHassSnapshot = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    // Avoid rebuilding the card for unrelated Home Assistant state changes.
    const entityIds = [
      ...WEEK_KEYS.flatMap((week) => [
        this._config?.[`delivery_week_${week}`],
        this._config?.[`recipe_count_week_${week}`],
      ]),
      this._config?.refresh_button,
      this._config?.calendar_button,
      this._config?.pdf_button,
    ];
    const snapshot = [
      hass.locale?.language,
      hass.language,
      hass.themes?.theme,
      hass.themes?.darkMode,
      ...entityIds.map((id) => (id ? hass.states?.[id] : undefined)),
    ];
    const previous = this._lastHassSnapshot;
    if (previous && previous.length === snapshot.length &&
        snapshot.every((value, index) => value === previous[index])) return;
    this._lastHassSnapshot = snapshot;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  _isFrench() {
    const lang =
      this._hass?.locale?.language ||
      this._hass?.language ||
      navigator.language ||
      "fr";
    return String(lang).toLowerCase().startsWith("fr");
  }

  _t(fr, en) {
    return this._isFrench() ? fr : en;
  }

  _state(entityId) {
    return entityId && this._hass ? this._hass.states[entityId] : undefined;
  }

  _deliveryEntity(week) {
    return this._state(this._config?.[`delivery_week_${week}`]);
  }

  _recipeEntity(week) {
    return this._state(this._config?.[`recipe_count_week_${week}`]);
  }

  _active(week) {
    const entity = this._deliveryEntity(week);
    if (!entity) return false;
    const value = entity.attributes?.active_delivery;
    if (typeof value === "boolean") return value;
    return !["non", "no", "unknown", "unavailable", "none", ""].includes(
      String(entity.state ?? "").toLowerCase()
    );
  }

  _availableWeeks() {
    if (!this._config) return WEEK_KEYS;
    if (this._config.show_empty_weeks !== false) return WEEK_KEYS;
    const active = WEEK_KEYS.filter((week) => this._active(week));
    return active.length ? active : WEEK_KEYS;
  }

  _pickDefaultWeek() {
    const visible = this._availableWeeks();
    const active = visible.find((week) => this._active(week));
    return active ?? visible[0] ?? 0;
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _formatServings(value) {
    if (value === null || value === undefined || value === "") return "";
    const text = String(value).trim();
    if (!text) return "";
    return text;
  }

  _recipeDetails(week) {
    const recipeSensor = this._recipeEntity(week);
    const rawDetails = recipeSensor?.attributes?.recipe_details;

    if (Array.isArray(rawDetails) && rawDetails.length) {
      return rawDetails.map((item) => ({
        name: item?.name || "",
        kitchen_duration_minutes:
          item?.kitchen_duration_minutes === null ||
          item?.kitchen_duration_minutes === undefined
            ? (
                item?.duration_minutes === null ||
                item?.duration_minutes === undefined
                  ? null
                  : Number(item.duration_minutes)
              )
            : Number(item.kitchen_duration_minutes),
        servings: item?.servings ?? null,
        image_url: item?.image_url ?? null,
      }));
    }

    // Backward compatibility with integrations exposing only `recipes`.
    const names = Array.isArray(recipeSensor?.attributes?.recipes)
      ? recipeSensor.attributes.recipes
      : [];

    return names.map((name) => ({
      name,
      kitchen_duration_minutes: null,
      servings: null,
      image_url: null,
    }));
  }

  _relativeDelivery(value) {
    if (!value || ["non", "no", "unknown", "unavailable"].includes(String(value).toLowerCase())) {
      return "";
    }

    const delivery = new Date(`${value}T12:00:00`);
    if (Number.isNaN(delivery.getTime())) return "";

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0, 0);
    const diffDays = Math.round((delivery.getTime() - today.getTime()) / 86400000);

    if (diffDays === 0) return this._t("aujourd’hui", "today");
    if (diffDays === 1) return this._t("demain", "tomorrow");
    if (diffDays === -1) return this._t("hier", "yesterday");
    if (diffDays > 1) return this._t(`dans ${diffDays} jours`, `in ${diffDays} days`);
    return this._t(`il y a ${Math.abs(diffDays)} jours`, `${Math.abs(diffDays)} days ago`);
  }

  _shortDate(week) {
    const delivery = this._deliveryEntity(week);
    if (!delivery || !this._active(week)) return "—";

    const parsed = new Date(`${delivery.state}T12:00:00`);
    if (Number.isNaN(parsed.getTime())) return "—";

    const locale =
      this._hass?.locale?.language ||
      this._hass?.language ||
      (this._isFrench() ? "fr-FR" : "en-GB");

    return new Intl.DateTimeFormat(locale, {
      day: "2-digit",
      month: "2-digit",
    }).format(parsed);
  }

  _recipeCount(week) {
    const entity = this._recipeEntity(week);
    let value = Number(entity?.state);
    if (Number.isFinite(value)) return value;
    return this._recipeDetails(week).length;
  }

  _totalRecipeCount() {
    return WEEK_KEYS.reduce(
      (total, week) => total + (this._active(week) ? this._recipeCount(week) : 0),
      0
    );
  }

  _activeBoxCount() {
    return WEEK_KEYS.filter((week) => this._active(week)).length;
  }

  _nextActiveWeek() {
    return WEEK_KEYS.find((week) => this._active(week)) ?? null;
  }

  _weekStatus(week) {
    const delivery = this._deliveryEntity(week);
    if (!delivery) {
      return {
        key: "missing",
        label: this._t("Entité absente", "Missing entity"),
        icon: "mdi:help-circle-outline",
      };
    }

    if (delivery.state === "unavailable") {
      return {
        key: "unavailable",
        label: this._t("Indisponible", "Unavailable"),
        icon: "mdi:alert-circle-outline",
      };
    }

    if (this._active(week)) {
      return {
        key: "active",
        label: this._t("Livraison active", "Active delivery"),
        icon: "mdi:truck-delivery",
      };
    }

    return {
      key: "empty",
      label: this._t("Aucune box", "No box"),
      icon: "mdi:calendar-remove-outline",
    };
  }

  _formatDate(value) {
    if (!value || ["non", "no", "unknown", "unavailable"].includes(String(value).toLowerCase())) {
      return this._t("Aucune livraison", "No delivery");
    }

    const parsed = new Date(`${value}T12:00:00`);
    if (Number.isNaN(parsed.getTime())) return value;

    const locale =
      this._hass?.locale?.language ||
      this._hass?.language ||
      (this._isFrench() ? "fr-FR" : "en-GB");

    return new Intl.DateTimeFormat(locale, {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(parsed);
  }

  _formatTime(value) {
    if (value === null || value === undefined || value === "") return "";
    const raw = String(value).trim();
    const match = raw.match(/^(\d{1,2})(?::|h)?(\d{2})?$/i);
    if (!match) return raw;
    const hh = String(match[1]).padStart(2, "0");
    const mm = String(match[2] || "00").padStart(2, "0");
    return this._isFrench() ? `${hh}h${mm}` : `${hh}:${mm}`;
  }

  _weekLabel(week) {
    if (week === 0) return "S0";
    return `S+${week}`;
  }

  _weekLongLabel(week) {
    if (week === 0) return this._t("Cette semaine", "This week");
    if (week === 1) return this._t("Semaine prochaine", "Next week");
    return this._t(`Dans ${week} semaines`, `In ${week} weeks`);
  }

  _calendarUrl() {
    const value = String(this._config?.calendar_url || "").trim();
    if (!value) return "";

    // Full external URLs.
    if (/^https?:\/\//i.test(value)) return value;

    // Other explicit URI schemes (for example homeassistant://).
    if (/^[a-z][a-z0-9+.-]*:/i.test(value)) return value;

    // Home Assistant internal path.
    if (value.startsWith("/")) return value;

    // A hostname entered without a scheme.
    if (/^[^\s/]+\.[^\s/]+(?:\/.*)?$/i.test(value)) {
      return `https://${value}`;
    }

    // Convenience: "calendar" or "lovelace/quitoque" becomes an HA path.
    return `/${value.replace(/^\/+/, "")}`;
  }

  async _pressButton(entityId, actionName) {
    if (!entityId || !this._hass?.states?.[entityId] || this._busy) return;

    this._busy = true;
    this._busyAction = actionName;
    this._render();

    try {
      await this._hass.callService("button", "press", { entity_id: entityId });
    } catch (error) {
      console.error("Quitoque Card: button press failed", error);
    } finally {
      window.setTimeout(() => {
        this._busy = false;
        this._busyAction = null;
        this._render();
      }, 900);
    }
  }

  async _cleanupPdfs() {
    if (this._busy || !this._hass) return;

    this._busy = true;
    this._busyAction = "cleanup";
    this._render();

    try {
      const serviceData = {};
      const configEntryId = String(this._config?.config_entry_id || "").trim();
      if (configEntryId) serviceData.config_entry_id = configEntryId;
      await this._hass.callService("quitoque", "cleanup_pdfs", serviceData);
    } catch (error) {
      console.error("Quitoque Card: PDF cleanup failed", error);
    } finally {
      window.setTimeout(() => {
        this._busy = false;
        this._busyAction = null;
        this._render();
      }, 900);
    }
  }

  _styles() {
    return `
      :host {
        display: block;
      }

      ha-card {
        overflow: hidden;
        padding: 0;
      }

      .card {
        padding: 18px;
      }

      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 16px;
      }

      .title-group {
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 0;
      }

      .logo {
        width: 44px;
        height: 44px;
        border-radius: 14px;
        display: grid;
        place-items: center;
        flex: 0 0 auto;
        background: var(--secondary-background-color);
        font-size: 25px;
      }

      .title {
        font-size: 21px;
        font-weight: 700;
        color: var(--primary-text-color);
        line-height: 1.15;
      }

      .subtitle {
        margin-top: 4px;
        font-size: 13px;
        color: var(--secondary-text-color);
      }

      .header-summary {
        flex: 0 0 auto;
        text-align: right;
        color: var(--secondary-text-color);
        font-size: 12px;
        line-height: 1.45;
      }

      .header-summary strong {
        display: block;
        color: var(--primary-text-color);
        font-size: 14px;
      }

      .header-right {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 10px;
        flex: 0 0 auto;
      }

      .header-calendar {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        min-height: 38px;
        padding: 7px 10px;
        border-radius: 10px;
        text-decoration: none;
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
        font-size: 12px;
        font-weight: 700;
        white-space: nowrap;
      }

      .header-calendar:hover {
        filter: brightness(.98);
      }

      .header-calendar ha-icon {
        --mdc-icon-size: 18px;
      }

      .weeks {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 7px;
        margin-bottom: 16px;
      }

      .week {
        border: 0;
        border-radius: 12px;
        padding: 8px 4px 7px;
        cursor: pointer;
        font: inherit;
        background: var(--secondary-background-color);
        color: var(--secondary-text-color);
        transition: transform .12s ease, background .12s ease;
        position: relative;
      }

      .week:hover {
        transform: translateY(-1px);
      }

      .week.selected {
        background: var(--primary-color);
        color: var(--text-primary-color, #fff);
        font-weight: 700;
      }

      .week::after {
        content: "";
        width: 7px;
        height: 7px;
        border-radius: 50%;
        position: absolute;
        right: 7px;
        top: 7px;
        background: var(--disabled-text-color);
      }

      .week.status-active::after {
        background: var(--success-color, #43a047);
      }

      .week.status-unavailable::after,
      .week.status-missing::after {
        background: var(--error-color, #db4437);
      }

      .week.selected::after {
        background: currentColor;
        opacity: .9;
      }

      .week-label {
        display: block;
        font-weight: 700;
      }

      .week-date {
        display: block;
        margin-top: 3px;
        font-size: 10px;
        opacity: .82;
      }

      .week-recipes {
        display: block;
        margin-top: 2px;
        font-size: 10px;
        opacity: .82;
      }

      .week-relative {
        display: block;
        margin-top: 2px;
        font-size: 9px;
        line-height: 1.1;
        opacity: .76;
      }

      .main {
        border-radius: 16px;
        background: var(--secondary-background-color);
        padding: 16px;
      }

      .delivery-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
      }

      .eyebrow {
        color: var(--secondary-text-color);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: .04em;
        text-transform: uppercase;
      }

      .delivery-date {
        margin-top: 5px;
        color: var(--primary-text-color);
        font-size: 18px;
        font-weight: 700;
        line-height: 1.3;
      }

      .slot {
        margin-top: 5px;
        color: var(--secondary-text-color);
        font-size: 13px;
      }

      .relative {
        margin-top: 6px;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 12px;
        font-weight: 700;
        color: var(--primary-color);
      }

      .status-row {
        margin-top: 8px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: var(--secondary-text-color);
        font-size: 12px;
      }

      .status-row ha-icon,
      .relative ha-icon {
        --mdc-icon-size: 16px;
      }

      .active-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        margin-top: 9px;
        padding: 4px 8px;
        border-radius: 999px;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: .03em;
        text-transform: uppercase;
        color: var(--success-color, #43a047);
        background: color-mix(in srgb, var(--success-color, #43a047) 12%, transparent);
      }

      .empty-delivery {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 18px 4px 4px;
        color: var(--secondary-text-color);
      }

      .empty-delivery ha-icon {
        --mdc-icon-size: 27px;
      }

      .count {
        min-width: 62px;
        text-align: center;
        border-radius: 14px;
        padding: 9px 10px;
        background: var(--card-background-color);
      }

      .count-number {
        font-size: 22px;
        line-height: 1;
        font-weight: 800;
        color: var(--primary-text-color);
      }

      .count-label {
        margin-top: 4px;
        font-size: 11px;
        color: var(--secondary-text-color);
      }

      .recipes-wrap {
        margin-top: 16px;
      }

      .recipes-toggle {
        width: 100%;
        appearance: none;
        border: 0;
        background: transparent;
        color: var(--primary-text-color);
        cursor: pointer;
        padding: 0 0 8px 0;
        font: inherit;
        font-size: 13px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }

      .recipes-toggle ha-icon {
        transition: transform .15s ease;
      }

      .recipes-toggle.expanded ha-icon {
        transform: rotate(180deg);
      }

      .recipes {
        display: grid;
        gap: 8px;
      }

      .recipes.hidden {
        display: none;
      }

      .recipe {
        display: grid;
        grid-template-columns: var(--quitoque-image-width, 86px) 1fr;
        gap: 12px;
        min-height: 82px;
        padding: 10px;
        border-radius: 13px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        overflow: hidden;
      }

      .recipe.no-image {
        grid-template-columns: 1fr;
        min-height: auto;
      }

      .recipe-image {
        width: var(--quitoque-image-width, 86px);
        height: var(--quitoque-image-height, 82px);
        border-radius: 10px;
        object-fit: cover;
        background: var(--secondary-background-color);
      }

      .recipe-image-placeholder {
        width: var(--quitoque-image-width, 86px);
        height: var(--quitoque-image-height, 82px);
        border-radius: 10px;
        display: grid;
        place-items: center;
        background: var(--secondary-background-color);
        color: var(--secondary-text-color);
      }

      .recipe-image-placeholder ha-icon {
        --mdc-icon-size: 30px;
      }

      .recipe-body {
        min-width: 0;
        display: flex;
        flex-direction: column;
        justify-content: center;
      }

      .recipe-name {
        font-size: 14px;
        line-height: 1.35;
        font-weight: 700;
        color: var(--primary-text-color);
      }

      .recipe-meta {
        margin-top: 8px;
        display: flex;
        flex-wrap: wrap;
        gap: 7px 12px;
        color: var(--secondary-text-color);
        font-size: 12px;
      }

      .recipe-meta-item {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        white-space: nowrap;
      }

      .recipe-meta-item ha-icon {
        --mdc-icon-size: 15px;
      }

      .empty {
        margin-top: 14px;
        color: var(--secondary-text-color);
        font-size: 14px;
      }


      .actions {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 8px;
        margin: 0 0 14px 0;
      }

      .action {
        appearance: none;
        box-sizing: border-box;
        text-decoration: none;
        border: 0;
        border-radius: 12px;
        min-height: 45px;
        padding: 9px 7px;
        cursor: pointer;
        font: inherit;
        font-size: 12px;
        font-weight: 600;
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 7px;
      }

      .action:hover {
        filter: brightness(.98);
      }

      .action:disabled {
        cursor: default;
        opacity: .42;
      }

      .action.busy {
        opacity: .85;
      }

      .action.busy ha-icon {
        animation: qt-spin .8s linear infinite;
      }

      ha-icon {
        --mdc-icon-size: 19px;
      }

      .card.image-small {
        --quitoque-image-width: 64px;
        --quitoque-image-height: 64px;
      }

      .card.image-medium {
        --quitoque-image-width: 86px;
        --quitoque-image-height: 82px;
      }

      .card.image-large {
        --quitoque-image-width: 118px;
        --quitoque-image-height: 104px;
      }

      .planning {
        display: grid;
        gap: 8px;
      }

      .planning-row {
        display: grid;
        grid-template-columns: 48px 1fr auto;
        align-items: center;
        gap: 10px;
        min-height: 48px;
        padding: 8px 11px;
        border-radius: 12px;
        background: var(--secondary-background-color);
      }

      .planning-row.inactive {
        opacity: .62;
      }

      .planning-week {
        font-weight: 800;
        color: var(--primary-text-color);
      }

      .planning-main {
        min-width: 0;
      }

      .planning-date {
        font-size: 13px;
        font-weight: 700;
        color: var(--primary-text-color);
      }

      .planning-slot {
        margin-top: 2px;
        font-size: 11px;
        color: var(--secondary-text-color);
      }

      .planning-count {
        white-space: nowrap;
        font-size: 12px;
        color: var(--secondary-text-color);
      }

      .compact-summary {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 7px;
        margin-top: 12px;
      }

      .compact-week {
        border-radius: 11px;
        background: var(--secondary-background-color);
        padding: 8px 5px;
        text-align: center;
        font-size: 11px;
        color: var(--secondary-text-color);
      }

      .compact-week strong {
        display: block;
        margin-top: 3px;
        font-size: 13px;
        color: var(--primary-text-color);
      }

      .diagnostic {
        margin-top: 12px;
        color: var(--secondary-text-color);
        font-size: 11px;
        text-align: right;
      }

      @keyframes qt-spin {
        to { transform: rotate(360deg); }
      }

      @media (max-width: 420px) {
        .card {
          padding: 14px;
        }

        .header {
          align-items: flex-start;
        }

        .header-summary {
          display: none;
        }

        .header-right {
          gap: 6px;
        }

        .header-calendar {
          min-height: 36px;
          padding: 6px 8px;
        }

        .header-calendar span {
          display: none;
        }

        .weeks {
          display: flex;
          overflow-x: auto;
          scroll-snap-type: x proximity;
          scrollbar-width: none;
          padding-bottom: 3px;
        }

        .weeks::-webkit-scrollbar {
          display: none;
        }

        .week {
          flex: 0 0 76px;
          scroll-snap-align: start;
        }

        .delivery-head {
          gap: 8px;
        }

        .delivery-date {
          font-size: 16px;
        }

        .actions {
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 6px;
        }

        .action {
          min-width: 0;
          padding: 8px 4px;
          font-size: 11px;
          gap: 4px;
        }

        .recipe {
          grid-template-columns: var(--quitoque-image-width, 72px) 1fr;
        }

        .card.image-large {
          --quitoque-image-width: 96px;
          --quitoque-image-height: 88px;
        }
      }
    `;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;

    if (!this._hass) {
      this.shadowRoot.innerHTML = `
        <style>${this._styles()}</style>
        <ha-card><div class="card">${this._escape(this._config.title)}</div></ha-card>
      `;
      return;
    }

    const visibleWeeks = this._availableWeeks();
    if (this._selectedWeek === null || !visibleWeeks.includes(this._selectedWeek)) {
      this._selectedWeek = this._pickDefaultWeek();
    }

    const week = this._selectedWeek;
    const delivery = this._deliveryEntity(week);
    const recipeSensor = this._recipeEntity(week);
    const active = this._active(week);
    const weekStatus = this._weekStatus(week);
    const relativeDelivery = active ? this._relativeDelivery(delivery?.state) : "";
    const totalRecipes = this._totalRecipeCount();
    const activeBoxCount = this._activeBoxCount();
    const nextActiveWeek = this._nextActiveWeek();

    const recipeDetails = this._recipeDetails(week);
    const recipeNames = recipeDetails.map((recipe) => recipe.name).filter(Boolean);

    let recipeCount = Number(recipeSensor?.state);
    if (!Number.isFinite(recipeCount)) recipeCount = recipeDetails.length;

    const weekNumber = delivery?.attributes?.week;
    const start = this._formatTime(delivery?.attributes?.delivery_start_hour);
    const end = this._formatTime(delivery?.attributes?.delivery_end_hour);
    const slot =
      start || end
        ? `${this._t("Créneau", "Time slot")} : ${start || "?"}${end ? ` → ${end}` : ""}`
        : "";


    const refreshEntity = this._config.refresh_button;
    const calendarEntity = this._config.calendar_button;
    const pdfEntity = this._config.pdf_button;
    const calendarUrl = this._calendarUrl();

    const refreshAvailable =
      !!this._state(refreshEntity) &&
      this._state(refreshEntity).state !== "unavailable";
    const calendarAvailable =
      !!this._state(calendarEntity) &&
      this._state(calendarEntity).state !== "unavailable";
    const pdfAvailable =
      !!this._state(pdfEntity) &&
      this._state(pdfEntity).state !== "unavailable";

    const weeksHtml = visibleWeeks
      .map((w) => {
        const status = this._weekStatus(w);
        const count = this._recipeCount(w);
        const relative = this._active(w)
          ? this._relativeDelivery(this._deliveryEntity(w)?.state)
          : "";
        return `
          <button
            class="week ${w === week ? "selected" : ""} status-${status.key}"
            data-week="${w}"
            title="${this._escape(`${this._weekLongLabel(w)} · ${status.label}`)}"
          >
            <span class="week-label">${this._weekLabel(w)}</span>
            <span class="week-date">${this._escape(this._shortDate(w))}</span>
            <span class="week-recipes">${this._active(w) ? `🍽 ${count}` : "—"}</span>
            ${relative ? `<span class="week-relative">${this._escape(relative)}</span>` : ""}
          </button>
        `;
      })
      .join("");

    const recipesListHtml = recipeDetails.length
      ? `
          ${recipeDetails
            .map((recipe) => {

              const kitchenDuration =
                Number.isFinite(recipe.kitchen_duration_minutes) &&
                recipe.kitchen_duration_minutes > 0
                  ? `${recipe.kitchen_duration_minutes} min`
                  : "";

              const servings = this._formatServings(recipe.servings);
              const imageUrl =
                typeof recipe.image_url === "string" &&
                /^https?:\/\//i.test(recipe.image_url)
                  ? recipe.image_url
                  : "";

              const showImage = this._config.show_recipe_images !== false;
              const imageHtml = showImage
                ? imageUrl
                  ? `<img
                       class="recipe-image"
                       src="${this._escape(imageUrl)}"
                       alt="${this._escape(recipe.name)}"
                       loading="lazy"
                       referrerpolicy="no-referrer"
                     >`
                  : `<div class="recipe-image-placeholder">
                       <ha-icon icon="mdi:chef-hat"></ha-icon>
                     </div>`
                : "";

              const metaHtml =
                kitchenDuration || servings
                  ? `
                    <div class="recipe-meta">
                      ${
                        kitchenDuration
                          ? `<span class="recipe-meta-item" title="${this._t("Temps en cuisine", "Kitchen time")}">
                               <ha-icon icon="mdi:chef-hat"></ha-icon>
                               ${this._t("Cuisine", "Kitchen")} ${this._escape(kitchenDuration)}
                             </span>`
                          : ""
                      }
                      ${
                        servings
                          ? `<span class="recipe-meta-item">
                               <ha-icon icon="mdi:account-group-outline"></ha-icon>
                               ${this._escape(servings)}
                             </span>`
                          : ""
                      }
                    </div>
                  `
                  : "";

              return `
                <div class="recipe ${showImage ? "" : "no-image"}">
                  ${imageHtml}
                  <div class="recipe-body">
                    <div class="recipe-name">${this._escape(recipe.name)}</div>
                    ${metaHtml}
                  </div>
                </div>
              `;
            })
            .join("")}
      `
      : `
        <div class="empty">
          ${active
            ? this._t("Aucune recette disponible.", "No recipe available.")
            : this._t("Aucune box active pour cette semaine.", "No active box for this week.")}
        </div>
      `;

    const recipesHtml =
      this._config.display_mode === "compact"
        ? ""
        : `
          <div class="recipes-wrap">
            <button class="recipes-toggle ${this._recipesExpanded ? "expanded" : ""}" data-action="toggle-recipes">
              <span>${this._t("Recettes", "Recipes")} (${this._escape(recipeCount)})</span>
              <ha-icon icon="mdi:chevron-down"></ha-icon>
            </button>
            <div class="recipes ${this._recipesExpanded ? "" : "hidden"}">
              ${recipesListHtml}
            </div>
          </div>
        `;

    const compactSummaryHtml =
      this._config.display_mode === "compact"
        ? `
          <div class="compact-summary">
            ${WEEK_KEYS.map((w) => {
              const status = this._weekStatus(w);
              const recipes = this._recipeEntity(w);
              let count = Number(recipes?.state);
              if (!Number.isFinite(count)) count = 0;
              return `
                <div class="compact-week" title="${this._escape(status.label)}">
                  ${this._weekLabel(w)}
                  <strong>${status.key === "active" ? `${count} 🍽️` : "—"}</strong>
                </div>
              `;
            }).join("")}
          </div>
        `
        : "";

    const planningHtml =
      this._config.display_mode === "planning"
        ? `
          <div class="planning">
            ${visibleWeeks.map((w) => {
              const deliveryState = this._deliveryEntity(w);
              const isActive = this._active(w);
              const start = this._formatTime(deliveryState?.attributes?.delivery_start_hour);
              const end = this._formatTime(deliveryState?.attributes?.delivery_end_hour);
              const slot = start || end ? `${start || "?"}${end ? ` → ${end}` : ""}` : "";
              return `
                <div class="planning-row ${isActive ? "" : "inactive"}">
                  <div class="planning-week">${this._weekLabel(w)}</div>
                  <div class="planning-main">
                    <div class="planning-date">
                      ${isActive
                        ? this._escape(this._formatDate(deliveryState?.state))
                        : this._t("Aucune livraison", "No delivery")}
                    </div>
                    ${slot ? `<div class="planning-slot">${this._escape(slot)}</div>` : ""}
                  </div>
                  <div class="planning-count">
                    ${isActive ? `${this._recipeCount(w)} 🍽️` : "—"}
                  </div>
                </div>
              `;
            }).join("")}
          </div>
        `
        : "";

    const busyLabels = {
      refresh: this._t("Actualisation…", "Refreshing…"),
      calendar: this._t("Synchro…", "Syncing…"),
      pdf: this._t("Génération PDF…", "Generating PDF…"),
      cleanup: this._t("Suppression…", "Deleting…"),
    };

    const actionsHtml =
      this._config.show_actions === false
        ? ""
        : `
          <div class="actions">
            <button class="action ${this._busyAction === "refresh" ? "busy" : ""}" data-action="refresh" ${refreshAvailable && !this._busy ? "" : "disabled"}>
              <ha-icon icon="mdi:refresh"></ha-icon>
              <span>${this._busyAction === "refresh" ? busyLabels.refresh : this._t("Actualiser", "Refresh")}</span>
            </button>

            <button class="action ${this._busyAction === "calendar" ? "busy" : ""}" data-action="calendar" ${calendarAvailable && !this._busy ? "" : "disabled"}>
              <ha-icon icon="mdi:calendar-import"></ha-icon>
              <span>${this._busyAction === "calendar" ? busyLabels.calendar : this._t("Calendrier", "Calendar")}</span>
            </button>

            <button class="action ${this._busyAction === "pdf" ? "busy" : ""}" data-action="pdf" ${pdfAvailable && !this._busy ? "" : "disabled"}>
              <ha-icon icon="mdi:file-pdf-box"></ha-icon>
              <span>${this._busyAction === "pdf" ? busyLabels.pdf : "PDF"}</span>
            </button>

            <button class="action ${this._busyAction === "cleanup" ? "busy" : ""}" data-action="cleanup" ${!this._busy ? "" : "disabled"}>
              <ha-icon icon="mdi:delete-sweep-outline"></ha-icon>
              <span>${this._busyAction === "cleanup" ? busyLabels.cleanup : this._t("Supprimer", "Delete")}</span>
            </button>

          </div>
        `;

    // Preserve already loaded images when a relevant entity does change.
    const previousImages = new Map();
    this.shadowRoot.querySelectorAll("img.recipe-image").forEach((img) => {
      const url = img.getAttribute("src");
      if (!previousImages.has(url)) previousImages.set(url, []);
      previousImages.get(url).push(img);
    });

    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <ha-card>
        <div class="card image-${this._escape(this._config.image_size || "medium")}">
          <div class="header">
            <div class="title-group">
              <div class="logo">🍽️</div>
              <div>
                <div class="title">${this._escape(this._config.title || "Quitoque")}</div>
                <div class="subtitle">
                  ${weekNumber
                    ? `${this._escape(this._weekLongLabel(week))} · S${this._escape(weekNumber)}`
                    : this._escape(this._weekLongLabel(week))}
                </div>
              </div>
            </div>
            <div class="header-right">
              <div class="header-summary">
                <strong>${activeBoxCount} ${this._t("box", "box")}${activeBoxCount > 1 ? " •" : ""}</strong>
                ${totalRecipes} ${this._t("recettes prévues", "planned recipes")}
              </div>

              ${calendarUrl
                ? `<a
                     class="header-calendar"
                     href="${this._escape(calendarUrl)}"
                     target="_blank"
                     rel="noopener noreferrer"
                     title="${this._escape(this._config.calendar_url_name || this._t("Ouvrir calendrier", "Open calendar"))}"
                   >
                     <ha-icon icon="mdi:calendar-month"></ha-icon>
                     <span>${this._escape(this._config.calendar_url_name || this._t("Ouvrir calendrier", "Open calendar"))}</span>
                   </a>`
                : ""}
            </div>
          </div>

          ${actionsHtml}

          <div class="weeks">${weeksHtml}</div>

          ${this._config.display_mode === "planning" ? planningHtml : `
          <div class="main">
            <div class="delivery-head">
              <div>
                <div class="eyebrow">
                  ${active ? this._t("Prochaine box", "Delivery") : this._t("Livraison", "Delivery")}
                </div>
                <div class="delivery-date">
                  ${this._escape(active ? this._formatDate(delivery?.state) : this._t("Aucune livraison", "No delivery"))}
                </div>
                ${slot ? `<div class="slot">${this._escape(slot)}</div>` : ""}
                ${relativeDelivery
                  ? `<div class="relative"><ha-icon icon="mdi:calendar-clock"></ha-icon>${this._escape(relativeDelivery)}</div>`
                  : ""}
                <div class="status-row">
                  <ha-icon icon="${weekStatus.icon}"></ha-icon>
                  ${this._escape(weekStatus.label)}
                </div>
                ${active
                  ? `<div class="active-badge"><ha-icon icon="mdi:check-circle"></ha-icon>${this._t("Box active", "Active box")}</div>`
                  : ""}
              </div>

              <div class="count">
                <div class="count-number">${this._escape(recipeCount)}</div>
                <div class="count-label">${this._t("recette(s)", "recipe(s)")}</div>
              </div>
            </div>

            ${active
              ? recipesHtml
              : `<div class="empty-delivery">
                   <ha-icon icon="mdi:calendar-remove-outline"></ha-icon>
                   <span>${this._t("Aucune livraison prévue pour cette semaine.", "No delivery planned for this week.")}</span>
                 </div>`}

          </div>
          `}

          ${compactSummaryHtml}

          <div class="diagnostic">
            Quitoque Card v${QUITOQUE_CARD_VERSION}
          </div>
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelectorAll("img.recipe-image").forEach((img) => {
      const matches = previousImages.get(img.getAttribute("src"));
      if (!matches?.length) return;
      const existing = matches.shift();
      existing.alt = img.alt;
      img.replaceWith(existing);
    });

    this.shadowRoot.querySelectorAll(".week").forEach((button) => {
      button.addEventListener("click", () => {
        this._selectedWeek = Number(button.dataset.week);
        this._render();
      });
    });

    const recipesToggle = this.shadowRoot.querySelector('[data-action="toggle-recipes"]');
    if (recipesToggle) {
      recipesToggle.addEventListener("click", () => {
        this._recipesExpanded = !this._recipesExpanded;
        this._render();
      });
    }

    const actionMap = {
      refresh: refreshEntity,
      calendar: calendarEntity,
      pdf: pdfEntity,
    };

    this.shadowRoot.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.action === "cleanup") {
          this._cleanupPdfs();
          return;
        }
        this._pressButton(actionMap[button.dataset.action], button.dataset.action);
      });
    });
  }
}

class QuitoqueCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = { ...DEFAULT_CONFIG };
  }

  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...config };

    // Render only once. Home Assistant calls setConfig again after every
    // config-changed event. Rebuilding the whole DOM here would close menus
    // and reset text fields while the user is editing them.
    if (!this.shadowRoot || !this.shadowRoot.hasChildNodes()) {
      this._render();
      return;
    }

    // Keep native entity pickers synchronized without recreating them.
    this.shadowRoot
      .querySelectorAll("ha-entity-picker[data-entity-key]")
      .forEach((picker) => {
        const key = picker.dataset.entityKey;
        const value = this._config[key] || "";
        if (picker.value !== value) picker.value = value;
      });

    // Keep HA selectors synchronized, but do not overwrite the selector that
    // currently has keyboard focus.
    this.shadowRoot
      .querySelectorAll("ha-selector[data-selector-key]")
      .forEach((selector) => {
        const key = selector.dataset.selectorKey;
        const defaults = {
          display_mode: "detailed",
          image_size: "medium",
          calendar_url: "",
          calendar_url_name: "Ouvrir calendrier",
          config_entry_id: "",
        };
        const value = this._config[key] ?? defaults[key] ?? "";

        // The HA dropdown remains mounted across config changes. Its value
        // is updated on value-changed, so do not reset an open dropdown.
        if (selector.matches(":focus-within")) return;
        if (selector.value !== value) selector.value = value;
      });
  }

  set hass(hass) {
    this._hass = hass;

    // Important: do not rebuild the editor on every Home Assistant state update.
    // Recreating ha-entity-picker while its dropdown is open closes the menu.
    if (!this.shadowRoot || !this.shadowRoot.hasChildNodes()) {
      this._render();
      return;
    }

    this.shadowRoot
      .querySelectorAll("ha-entity-picker[data-entity-key]")
      .forEach((picker) => {
        picker.hass = hass;
      });

    this.shadowRoot
      .querySelectorAll("ha-selector[data-selector-key]")
      .forEach((selector) => {
        selector.hass = hass;
      });
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _entities(domain) {
    if (!this._hass) return [];
    return Object.values(this._hass.states)
      .filter((state) => state.entity_id.startsWith(`${domain}.`))
      .sort((a, b) => {
        const an = a.attributes?.friendly_name || a.entity_id;
        const bn = b.attributes?.friendly_name || b.entity_id;
        return an.localeCompare(bn);
      });
  }

  _select(key, label, domain) {
    return `
      <label class="entity-field">
        <span>${this._escape(label)}</span>
        <ha-entity-picker
          data-entity-key="${this._escape(key)}"
          data-domain="${this._escape(domain)}"
        ></ha-entity-picker>
      </label>
    `;
  }

  _emit() {
    const event = new CustomEvent("config-changed", {
      detail: { config: { ...this._config } },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        .editor {
          display: grid;
          gap: 18px;
          padding: 4px 0 8px;
        }

        .section {
          display: grid;
          gap: 10px;
        }

        .section-title {
          font-weight: 700;
          color: var(--primary-text-color);
          font-size: 14px;
        }

        label {
          display: grid;
          gap: 5px;
          color: var(--secondary-text-color);
          font-size: 12px;
        }

        input[type="text"] {
          box-sizing: border-box;
          width: 100%;
          min-height: 42px;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 7px 10px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          font: inherit;
          font-size: 14px;
        }

        ha-selector {
          display: block;
          width: 100%;
        }

        .ha-selector-field {
          gap: 7px;
        }

        ha-entity-picker {
          display: block;
          width: 100%;
        }

        .entity-field {
          gap: 7px;
        }

        .check {
          display: flex;
          align-items: center;
          grid-template-columns: none;
          gap: 9px;
          color: var(--primary-text-color);
          font-size: 14px;
        }

        .check input {
          width: 18px;
          height: 18px;
        }

        .hint {
          color: var(--secondary-text-color);
          font-size: 12px;
          line-height: 1.4;
        }
      </style>

      <div class="editor">
        <div class="section">
          <div class="section-title">Affichage</div>

          <label>
            <span>Titre</span>
            <input data-key="title" type="text" value="${this._escape(this._config.title || "")}">
          </label>

          <label class="ha-selector-field">
            <span>Mode d’affichage</span>
            <ha-selector data-selector-key="display_mode"></ha-selector>
          </label>

          <label class="check">
            <input data-key="show_empty_weeks" type="checkbox" ${this._config.show_empty_weeks !== false ? "checked" : ""}>
            <span>Afficher aussi les semaines sans livraison</span>
          </label>

          <label class="check">
            <input data-key="show_actions" type="checkbox" ${this._config.show_actions !== false ? "checked" : ""}>
            <span>Afficher les boutons d'action</span>
          </label>

          <label class="ha-selector-field">
            <span>URL du calendrier externe</span>
            <ha-selector data-selector-key="calendar_url"></ha-selector>
            <span class="hint">Exemples : <code>/calendar</code>, <code>calendar</code> ou <code>https://calendar.google.com/...</code></span>
          </label>

          <label class="ha-selector-field">
            <span>Nom du bouton calendrier</span>
            <ha-selector data-selector-key="calendar_url_name"></ha-selector>
          </label>

          <label class="check">
            <input data-key="recipes_collapsed" type="checkbox" ${this._config.recipes_collapsed === true ? "checked" : ""}>
            <span>Replier les recettes par défaut</span>
          </label>

          <label class="check">
            <input data-key="show_recipe_images" type="checkbox" ${this._config.show_recipe_images !== false ? "checked" : ""}>
            <span>Afficher les images des recettes</span>
          </label>

          <label class="ha-selector-field">
            <span>Taille des images</span>
            <ha-selector data-selector-key="image_size"></ha-selector>
          </label>
        </div>

        <div class="section">
          <div class="section-title">Livraisons S0 → S+4</div>
          ${this._select("delivery_week_0", "S0 — Livraison cette semaine", "sensor")}
          ${this._select("delivery_week_1", "S+1 — Livraison semaine prochaine", "sensor")}
          ${this._select("delivery_week_2", "S+2 — Livraison", "sensor")}
          ${this._select("delivery_week_3", "S+3 — Livraison", "sensor")}
          ${this._select("delivery_week_4", "S+4 — Livraison", "sensor")}
        </div>

        <div class="section">
          <div class="section-title">Recettes S0 → S+4</div>
          ${this._select("recipe_count_week_0", "S0 — Nombre de recettes", "sensor")}
          ${this._select("recipe_count_week_1", "S+1 — Nombre de recettes", "sensor")}
          ${this._select("recipe_count_week_2", "S+2 — Nombre de recettes", "sensor")}
          ${this._select("recipe_count_week_3", "S+3 — Nombre de recettes", "sensor")}
          ${this._select("recipe_count_week_4", "S+4 — Nombre de recettes", "sensor")}
        </div>

        <div class="section">
          <div class="section-title">Actions</div>
          ${this._select("refresh_button", "Actualiser", "button")}
          ${this._select("calendar_button", "Ajouter au calendrier", "button")}
          ${this._select("pdf_button", "Générer les PDF", "button")}
          <label class="ha-selector-field">
            <span>Instance Quitoque pour la suppression</span>
            <ha-selector data-selector-key="config_entry_id"></ha-selector>
            <span class="hint">Facultatif avec un seul compte Quitoque.</span>
          </label>
          <div class="hint">
            Les boutons indisponibles dans Home Assistant sont automatiquement désactivés dans la carte.
          </div>
        </div>
      </div>
    `;

    // Native Home Assistant entity pickers.
    this.shadowRoot.querySelectorAll("ha-entity-picker[data-entity-key]").forEach((picker) => {
      const key = picker.dataset.entityKey;
      const domain = picker.dataset.domain;

      picker.hass = this._hass;
      picker.value = this._config[key] || "";
      picker.includeDomains = domain ? [domain] : undefined;
      picker.allowCustomEntity = true;

      picker.addEventListener("value-changed", (event) => {
        const value = event.detail?.value ?? "";
        if (this._config[key] === value) return;

        this._config = {
          ...this._config,
          [key]: value,
        };
        this._emit();
      });
    });

    // Native Home Assistant selectors.
    const selectorDefinitions = {
      display_mode: {
        select: {
          mode: "dropdown",
          options: [
            { value: "detailed", label: "Détaillé" },
            { value: "compact", label: "Compact" },
            { value: "planning", label: "Planning" },
          ],
        },
      },
      image_size: {
        select: {
          mode: "dropdown",
          options: [
            { value: "small", label: "Petite" },
            { value: "medium", label: "Moyenne" },
            { value: "large", label: "Grande" },
          ],
        },
      },
      calendar_url: {
        text: {
          multiline: false,
        },
      },
      calendar_url_name: {
        text: {
          multiline: false,
        },
      },
      config_entry_id: {
        config_entry: {
          integration: "quitoque",
        },
      },
    };

    this.shadowRoot
      .querySelectorAll("ha-selector[data-selector-key]")
      .forEach((selector) => {
        const key = selector.dataset.selectorKey;

        selector.hass = this._hass;
        selector.selector = selectorDefinitions[key];
        const selectorDefaults = {
          display_mode: "detailed",
          image_size: "medium",
          calendar_url: "",
          calendar_url_name: "Ouvrir calendrier",
          config_entry_id: "",
        };

        selector.value =
          this._config[key] ??
          selectorDefaults[key] ??
          "";

        selector.addEventListener("value-changed", (event) => {
          const value = event.detail?.value;
          if (value === undefined || value === null) return;
          if (this._config[key] === value) return;

          this._config = {
            ...this._config,
            [key]: value,
          };

          // Keep the HA selector's controlled value in sync with the new
          // configuration before Home Assistant processes config-changed.
          // In particular, this allows selecting a previous option again.
          if (key === "display_mode" || key === "image_size") {
            selector.value = value;
          }
          this._emit();
        });
      });

    // Standard editor fields.
    this.shadowRoot.querySelectorAll("[data-key]").forEach((input) => {
      const eventName = input.type === "checkbox" ? "change" : "input";

      input.addEventListener(eventName, () => {
        const key = input.dataset.key;
        this._config = {
          ...this._config,
          [key]: input.type === "checkbox" ? input.checked : input.value,
        };
        this._emit();
      });
    });
  }
}

if (!customElements.get("quitoque-card")) {
  customElements.define("quitoque-card", QuitoqueCard);
}

if (!customElements.get("quitoque-card-editor")) {
  customElements.define("quitoque-card-editor", QuitoqueCardEditor);
}

window.customCards = window.customCards || [];

if (!window.customCards.some((card) => card.type === "quitoque-card")) {
  window.customCards.push({
    type: "quitoque-card",
    name: "Quitoque Card",
    description: "Livraisons, recettes et actions de l’intégration Quitoque.",
    preview: true,
  });
}

console.info(
  `%c QUITOQUE-CARD %c v${QUITOQUE_CARD_VERSION} `,
  "background:#7db343;color:white;font-weight:bold;padding:2px 5px;border-radius:3px 0 0 3px",
  "background:#333;color:white;padding:2px 5px;border-radius:0 3px 3px 0"
);
