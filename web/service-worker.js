self.addEventListener("push", (event) => {
  const payload = event.data?.json() || {};
  event.waitUntil(
    self.registration.showNotification(payload.title || "OCaml Jobs", {
      body: payload.body || "New matched opportunities are available.",
      data: { url: payload.url || "/#notifications" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
