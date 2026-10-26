const APP_PAGE = 'index.html';
const TAB_KEY = 'pixelforgeTabId';
const api = typeof browser !== 'undefined' ? browser : chrome;

async function rememberTab(tabId) {
  try {
    await api.storage.session.set({ [TAB_KEY]: tabId });
  } catch {
    return;
  }
}

async function storedTab() {
  try {
    const values = await api.storage.session.get(TAB_KEY);
    return values && typeof values[TAB_KEY] === 'number' ? values[TAB_KEY] : null;
  } catch {
    return null;
  }
}

async function openApp() {
  const tabId = await storedTab();
  if (tabId !== null) {
    try {
      const tab = await api.tabs.update(tabId, { active: true });
      if (tab && tab.windowId !== undefined) {
        try {
          await api.windows.update(tab.windowId, { focused: true });
        } catch {
          void 0;
        }
      }
      return;
    } catch {
      void 0;
    }
  }
  const tab = await api.tabs.create({ url: api.runtime.getURL(APP_PAGE) });
  if (tab && typeof tab.id === 'number') await rememberTab(tab.id);
}

api.action.onClicked.addListener(() => {
  openApp();
});

api.runtime.onInstalled.addListener(() => {
  openApp();
});
