import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { boot } from "./services/session";
import "./styles.css";

// Сначала справочники и вход через MAX, потом отрисовка:
// профиль из localStorage проверяется по списку городов с бэкенда.
boot().then((session) =>
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App session={session} />
    </React.StrictMode>,
  ),
);
