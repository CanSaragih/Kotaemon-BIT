function run() {
  // Create modern preloader IMMEDIATELY - no delay
  const modernPreloader = document.createElement("div");
  modernPreloader.className = "modern-preloader";
  modernPreloader.id = "modern-preloader";

  modernPreloader.innerHTML = `
    <div class="preloader-container">
      <div class="preloader-logo"></div>
      <div class="preloader-title">SIPADU AI TOOLS</div>
      <div class="preloader-subtitle">Sistem manajemen data dan metadata terpusat, terstruktur dan terdokumentasi</div>
      <div class="preloader-spinner"></div>
      <div class="preloader-progress">
        <div class="preloader-progress-bar"></div>
      </div>
      <div class="preloader-status">
        Memuat sistem<span class="preloader-dots"></span>
      </div>
    </div>
  `;

  // Insert immediately at the beginning of body
  document.body.insertBefore(modernPreloader, document.body.firstChild);

  // Hide any Gradio default loading immediately
  const hideGradioLoading = () => {
    const gradioLoadings = document.querySelectorAll(
      ".loading, .gradio-loading"
    );
    gradioLoadings.forEach((el) => (el.style.display = "none"));
  };
  hideGradioLoading();

  // Enhanced status updates
  const statusTexts = [
    "Memuat sistem",
    "Menginisialisasi komponen",
    "Mempersiapkan antarmuka",
    "Menghubungkan ke server",
    "Memuat konfigurasi",
    "Hampir selesai",
  ];

  let currentStatus = 0;
  const statusElement = modernPreloader.querySelector(".preloader-status");

  const statusInterval = setInterval(() => {
    if (currentStatus < statusTexts.length - 1) {
      currentStatus++;
      statusElement.innerHTML =
        statusTexts[currentStatus] + '<span class="preloader-dots"></span>';
    }
  }, 400); // Faster status updates

  // Enhanced hide preloader function
  function hidePreloader() {
    clearInterval(statusInterval);

    // Update final status
    statusElement.innerHTML = "Siap digunakan!";

    setTimeout(() => {
      modernPreloader.classList.add("fade-out");

      setTimeout(() => {
        if (modernPreloader && modernPreloader.parentNode) {
          modernPreloader.remove();
        }

        // Ensure gradio container is visible and ready
        const gradioContainer = document.querySelector(".gradio-container");
        if (gradioContainer) {
          gradioContainer.classList.add("loaded");
          gradioContainer.style.opacity = "1";
          gradioContainer.style.visibility = "visible";
        }
      }, 500);
    }, 200);
  }

  // Optimized timing for better UX
  const minDisplayTime = 1800; // Slightly reduced minimum time
  const startTime = Date.now();

  function checkAndHide() {
    const elapsedTime = Date.now() - startTime;
    const gradioContainer = document.querySelector(".gradio-container");

    if (gradioContainer && elapsedTime >= minDisplayTime) {
      // Additional check: ensure Gradio is actually ready
      const tabsLoaded = document.querySelector("#chat-tab");
      if (tabsLoaded) {
        hidePreloader();
        return;
      }
    }

    // Continue checking every 100ms
    setTimeout(checkAndHide, 100);
  }

  // Start checking immediately
  setTimeout(checkAndHide, minDisplayTime);

  // Continuously hide any Gradio loading that might appear
  const loadingWatcher = setInterval(() => {
    hideGradioLoading();
    // Stop watching after preloader is hidden
    if (!document.getElementById("modern-preloader")) {
      clearInterval(loadingWatcher);
    }
  }, 100);

  let main_parent = document.getElementById("chat-tab").parentNode;

  main_parent.childNodes[0].classList.add("header-bar");
  main_parent.style = "padding: 0; margin: 0";
  main_parent.parentNode.style = "gap: 0";
  main_parent.parentNode.parentNode.style = "padding: 0";

  // Add SIPADU clickable logo next to Chat tab
  function addSipaduLogo() {
    const tabNavContainer = document.querySelector(".tab-nav");
    if (tabNavContainer && !document.querySelector(".sipadu-logo")) {
      const logo = document.createElement("div");
      logo.className = "sipadu-logo";
      logo.title = "Kembali ke Dashboard SIPADU";

      // Add click handler for logo with modern notification
      logo.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        // Create modern confirmation modal instead of browser alert
        showSipaduConfirmation();
      });

      // Insert logo after the first tab button (Chat)
      const firstTabButton = tabNavContainer.querySelector("button");
      if (firstTabButton) {
        firstTabButton.parentNode.insertBefore(
          logo,
          firstTabButton.nextSibling
        );
        console.log("✅ SIPADU clickable logo added to header");
      }
    }
  }

  // Modern confirmation function using Gradio's notification system
  function showSipaduConfirmation() {
    // Create modern modal overlay
    const overlay = document.createElement("div");
    overlay.className = "sipadu-confirm-overlay";

    const modal = document.createElement("div");
    modal.className = "sipadu-confirm-modal";

    modal.innerHTML = `
      <div class="sipadu-confirm-header">
        <div class="sipadu-confirm-icon">🏠</div>
        <h3>Kembali ke Dashboard SIPADU</h3>
      </div>
      <div class="sipadu-confirm-body">
        <p>Anda akan keluar dari AI Tools dan menuju ke Dashboard SIPADU.</p>
        <p>Silakan tekan Lanjutkan untuk melanjutkan.</p>
      </div>
      <div class="sipadu-confirm-actions">
        <button class="sipadu-btn-cancel">Batal</button>
        <button class="sipadu-btn-confirm">Lanjutkan</button>
      </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Add animation
    setTimeout(() => {
      overlay.classList.add("sipadu-confirm-show");
    }, 10);

    // Handle buttons
    const cancelBtn = modal.querySelector(".sipadu-btn-cancel");
    const confirmBtn = modal.querySelector(".sipadu-btn-confirm");

    cancelBtn.addEventListener("click", () => {
      closeSipaduConfirmation(overlay);
    });

    confirmBtn.addEventListener("click", () => {
      closeSipaduConfirmation(overlay);
      // Show loading notification
      showSipaduNotification("Mengarahkan ke Dashboard SIPADU...", "info");

      // Get SIPADU URL from environment-based config with multiple fallbacks
      let sipaduUrl = "http://localhost.sipadubapelitbangbogor/home"; // Default fallback

      // Priority 1: Window SIPADU_CONFIG from server environment
      if (window.SIPADU_CONFIG && window.SIPADU_CONFIG.HOME_URL) {
        sipaduUrl = window.SIPADU_CONFIG.HOME_URL;
        console.log("🏠 Using SIPADU URL from server config:", sipaduUrl);
      }
      // Priority 2: Window SIPADU_CONFIG API_BASE (construct home URL)
      else if (window.SIPADU_CONFIG && window.SIPADU_CONFIG.API_BASE) {
        sipaduUrl = window.SIPADU_CONFIG.API_BASE + "/home";
        console.log("🏠 Using SIPADU URL from API_BASE:", sipaduUrl);
      }
      // Priority 3: Try to get from localStorage (if previously stored)
      else if (localStorage.getItem("sipadu_base_url")) {
        sipaduUrl = localStorage.getItem("sipadu_base_url") + "/home";
        console.log("🏠 Using SIPADU URL from localStorage:", sipaduUrl);
      } else {
        console.log("🏠 Using default SIPADU URL:", sipaduUrl);
      }

      console.log("🏠 Final redirect URL:", sipaduUrl);

      // Redirect after short delay
      setTimeout(() => {
        try {
          // Store the base URL for future use
          if (window.SIPADU_CONFIG && window.SIPADU_CONFIG.API_BASE) {
            localStorage.setItem(
              "sipadu_base_url",
              window.SIPADU_CONFIG.API_BASE
            );
          }

          console.log("🚀 Redirecting to:", sipaduUrl);
          window.location.href = sipaduUrl;
        } catch (error) {
          console.error("❌ Redirect failed:", error);
          showSipaduNotification(
            "Gagal mengarahkan ke SIPADU. Silakan buka manual.",
            "error"
          );
          // Fallback: open in new tab
          window.open(sipaduUrl, "_blank");
        }
      }, 800);
    });

    // Close on overlay click
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        closeSipaduConfirmation(overlay);
      }
    });

    // Close on ESC key
    const handleEscape = (e) => {
      if (e.key === "Escape") {
        closeSipaduConfirmation(overlay);
        document.removeEventListener("keydown", handleEscape);
      }
    };
    document.addEventListener("keydown", handleEscape);
  }

  function closeSipaduConfirmation(overlay) {
    overlay.classList.remove("sipadu-confirm-show");
    setTimeout(() => {
      if (overlay.parentNode) {
        overlay.parentNode.removeChild(overlay);
      }
    }, 300);
  }

  // Modern notification system (integrates with Gradio's notification)
  function showSipaduNotification(message, type = "info") {
    // Try to use Gradio's notification system if available
    if (window.gradio && window.gradio.client) {
      // Use Gradio's built-in notification
      console.log(`🔔 ${type.toUpperCase()}: ${message}`);
      return;
    }

    // Fallback: Create custom notification
    const notification = document.createElement("div");
    notification.className = `sipadu-notification sipadu-notification-${type}`;
    notification.innerHTML = `
      <div class="sipadu-notification-icon">
        ${
          type === "info"
            ? "ℹ️"
            : type === "success"
            ? "✅"
            : type === "warning"
            ? "⚠️"
            : "❌"
        }
      </div>
      <div class="sipadu-notification-message">${message}</div>
    `;

    // Add to container or create one
    let container = document.querySelector(".sipadu-notification-container");
    if (!container) {
      container = document.createElement("div");
      container.className = "sipadu-notification-container";
      document.body.appendChild(container);
    }

    container.appendChild(notification);

    // Show animation
    setTimeout(
      () => notification.classList.add("sipadu-notification-show"),
      10
    );

    // Auto remove after 3 seconds
    setTimeout(() => {
      notification.classList.remove("sipadu-notification-show");
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, 3000);
  }

  // Hide specific tabs from main navigation
  function hideSpecificTabs() {
    // Get all tab navigation buttons
    const tabNavButtons = document.querySelectorAll(".tab-nav button");

    // List of tab names to hide (Indonesian)
    const tabsToHide = ["Sumber Daya", "Pengaturan", "Bantuan"];

    tabNavButtons.forEach((button) => {
      const buttonText = button.textContent.trim();

      // Hide tabs that match our criteria
      if (tabsToHide.includes(buttonText)) {
        button.style.display = "none";
        console.log(`Hidden tab: ${buttonText}`);
      }
    });

    // Also hide by tab IDs
    const tabsToHideById = ["#resources-tab", "#settings-tab", "#help-tab"];
    tabsToHideById.forEach((tabId) => {
      const tabButton = document.querySelector(
        `${tabId} .tab-nav button, button[data-testid*="${tabId.slice(1)}"]`
      );
      if (tabButton) {
        tabButton.style.display = "none";
        console.log(`Hidden tab by ID: ${tabId}`);
      }
    });
  }

  // Add elements immediately
  addSipaduLogo();
  hideSpecificTabs();

  const version_node = document.createElement("p");
  version_node.innerHTML = "version: KH_APP_VERSION";
  version_node.style = "position: fixed; top: 10px; right: 10px;";
  main_parent.appendChild(version_node);

  // add favicon
  const favicon = document.createElement("link");
  favicon.rel = "icon";
  favicon.type = "image/svg+xml";
  favicon.href = "/favicon.ico";
  document.head.appendChild(favicon);

  // setup conversation dropdown placeholder
  let conv_dropdown = document.querySelector("#conversation-dropdown input");
  conv_dropdown.placeholder = "Telusuri Percakapan";

  // move info-expand-button
  let info_expand_button = document.getElementById("info-expand-button");
  let chat_info_panel = document.getElementById("info-expand");
  chat_info_panel.insertBefore(
    info_expand_button,
    chat_info_panel.childNodes[2]
  );

  // move toggle-side-bar button
  let chat_expand_button = document.getElementById("chat-expand-button");
  let chat_column = document.getElementById("main-chat-bot");
  let conv_column = document.getElementById("conv-settings-panel");

  // move setting close button
  let setting_tab_nav_bar = document.querySelector("#settings-tab .tab-nav");
  let setting_close_button = document.getElementById("save-setting-btn");
  if (setting_close_button) {
    setting_tab_nav_bar.appendChild(setting_close_button);
  }

  let default_conv_column_min_width = "min(300px, 100%)";
  conv_column.style.minWidth = default_conv_column_min_width;

  globalThis.toggleChatColumn = () => {
    let flex_grow = conv_column.style.flexGrow;
    if (flex_grow == "0") {
      conv_column.style.flexGrow = "1";
      conv_column.style.minWidth = default_conv_column_min_width;
    } else {
      conv_column.style.flexGrow = "0";
      conv_column.style.minWidth = "0px";
    }
  };

  chat_column.insertBefore(chat_expand_button, chat_column.firstChild);

  // move use mind-map checkbox
  let mindmap_checkbox = document.getElementById("use-mindmap-checkbox");
  let citation_dropdown = document.getElementById("citation-dropdown");
  let chat_setting_panel = document.getElementById("chat-settings-expand");
  chat_setting_panel.insertBefore(
    mindmap_checkbox,
    chat_setting_panel.childNodes[2]
  );
  chat_setting_panel.insertBefore(citation_dropdown, mindmap_checkbox);

  // move share conv checkbox
  let report_div = document.querySelector(
    "#report-accordion > div:nth-child(3) > div:nth-child(1)"
  );
  let share_conv_checkbox = document.getElementById("is-public-checkbox");
  if (share_conv_checkbox) {
    report_div.insertBefore(
      share_conv_checkbox,
      report_div.querySelector("button")
    );
  }

  // create slider toggle
  const is_public_checkbox = document.getElementById("suggest-chat-checkbox");
  const label_element = is_public_checkbox.getElementsByTagName("label")[0];
  const checkbox_span = is_public_checkbox.getElementsByTagName("span")[0];
  let new_div = document.createElement("div");

  label_element.classList.add("switch");
  is_public_checkbox.appendChild(checkbox_span);
  label_element.appendChild(new_div);

  // clpse
  globalThis.clpseFn = (id) => {
    var obj = document.getElementById("clpse-btn-" + id);
    obj.classList.toggle("clpse-active");
    var content = obj.nextElementSibling;
    if (content.style.display === "none") {
      content.style.display = "block";
    } else {
      content.style.display = "none";
    }
  };

  // store info in local storage
  globalThis.setStorage = (key, value) => {
    localStorage.setItem(key, value);
  };
  globalThis.getStorage = (key, value) => {
    let item = localStorage.getItem(key);
    return item ? item : value;
  };
  globalThis.removeFromStorage = (key) => {
    localStorage.removeItem(key);
  };

  // Function to scroll to given citation with ID
  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  globalThis.scrollToCitation = async (event) => {
    event.preventDefault();
    var citationId = event.target.getAttribute("id");

    await sleep(100);

    var modal = document.getElementById("pdf-modal");
    var citation = document.querySelector('mark[id="' + citationId + '"]');

    if (modal.style.display == "block") {
      var detail_elem = citation;
      while (detail_elem.tagName.toLowerCase() != "details") {
        detail_elem = detail_elem.parentElement;
      }
      detail_elem.getElementsByClassName("pdf-link").item(0).click();
    } else {
      if (citation) {
        citation.scrollIntoView({ behavior: "smooth" });
      }
    }
  };

  globalThis.fullTextSearch = () => {
    var bot_messages = document.querySelectorAll(
      "div#main-chat-bot div.message-row.bot-row"
    );
    var last_bot_message = bot_messages[bot_messages.length - 1];

    if (last_bot_message.classList.contains("text_selection")) {
      return;
    }

    last_bot_message.classList.add("text_selection");

    var evidences = document.querySelectorAll(
      "#html-info-panel > div:last-child > div > details.evidence div.evidence-content"
    );
    console.log("Indexing evidences", evidences);

    const segmenterEn = new Intl.Segmenter("en", { granularity: "sentence" });
    var all_segments = [];
    for (var evidence of evidences) {
      if (!evidence.parentElement.open) {
        continue;
      }
      var markmap_div = evidence.querySelector("div.markmap");
      if (markmap_div) {
        continue;
      }

      var evidence_content = evidence.textContent.replace(/[\r\n]+/g, " ");
      let sentence_it = segmenterEn
        .segment(evidence_content)
        [Symbol.iterator]();
      while ((sentence = sentence_it.next().value)) {
        let segment = sentence.segment.trim();
        if (segment) {
          all_segments.push({
            id: all_segments.length,
            text: segment,
          });
        }
      }
    }

    let miniSearch = new MiniSearch({
      fields: ["text"],
      storeFields: ["text"],
    });

    miniSearch.addAll(all_segments);

    last_bot_message.addEventListener("mouseup", () => {
      let selection = window.getSelection().toString();
      let results = miniSearch.search(selection);

      if (results.length == 0) {
        return;
      }
      let matched_text = results[0].text;
      console.log("query\n", selection, "\nmatched text\n", matched_text);

      var evidences = document.querySelectorAll(
        "#html-info-panel > div:last-child > div > details.evidence div.evidence-content"
      );
      var modal = document.getElementById("pdf-modal");

      evidences.forEach((evidence) => {
        evidence.querySelectorAll("mark").forEach((mark) => {
          mark.outerHTML = mark.innerText;
        });
      });

      for (var evidence of evidences) {
        var evidence_content = evidence.textContent.replace(/[\r\n]+/g, " ");
        if (evidence_content.includes(matched_text)) {
          let paragraphs = evidence.querySelectorAll("p, li");
          for (var p of paragraphs) {
            var p_content = p.textContent.replace(/[\r\n]+/g, " ");
            if (p_content.includes(matched_text)) {
              p.innerHTML = p_content.replace(
                matched_text,
                "<mark>" + matched_text + "</mark>"
              );
              console.log("highlighted", matched_text, "in", p);
              if (modal.style.display == "block") {
                var detail_elem = p;
                while (detail_elem.tagName.toLowerCase() != "details") {
                  detail_elem = detail_elem.parentElement;
                }
                detail_elem.getElementsByClassName("pdf-link").item(0).click();
              } else {
                p.scrollIntoView({ behavior: "smooth", block: "center" });
              }
              break;
            }
          }
        }
      }
    });
  };

  globalThis.spawnDocument = (content, options) => {
    let opt = {
      window: "",
      closeChild: true,
      childId: "_blank",
    };
    Object.assign(opt, options);
    if (
      content &&
      typeof content.toString == "function" &&
      content.toString().length
    ) {
      let child = window.open("", opt.childId, opt.window);
      child.document.write(content.toString());
      return child;
    }
  };

  globalThis.fillChatInput = (event) => {
    let chatInput = document.querySelector("#chat-input textarea");
    chatInput.value = "Explain " + event.target.textContent;
    var evt = new Event("change");
    chatInput.dispatchEvent(new Event("input", { bubbles: true }));
    chatInput.focus();
  };

  // Improve tab switching animation
  const tabButtons = document.querySelectorAll(".tab-nav button");
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      // Add transition effect to tabs
      const tabs = document.querySelectorAll(".tabitem");
      tabs.forEach((tab) => {
        tab.style.transition = "opacity 0.3s ease";
        tab.style.opacity = "0.5";
        setTimeout(() => {
          tab.style.opacity = "1";
        }, 300);
      });
    });
  });

  // Set up MutationObserver to catch dynamically loaded tabs
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === "childList") {
        hideSpecificTabs();
        addSipaduLogo();
      }
    });
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  setTimeout(() => {
    hideSpecificTabs();
    addSipaduLogo();
  }, 1000);

  setTimeout(() => {
    hideSpecificTabs();
    addSipaduLogo();
  }, 3000);
}
