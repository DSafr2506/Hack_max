import { test, expect } from "@playwright/test";
test("onboarding, persistence, filters, details and profile", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  const overflow = async () =>
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  await overflow();
  await page.getByRole("button", { name: "Приступить", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Далее", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "9 класс" }).click();
  await page.getByRole("button", { name: "Далее", exact: true }).click();
  await page.getByRole("searchbox").fill("Неттакогогорода");
  await expect(page.getByText(/Ничего не найдено/)).toBeVisible();
  await page.getByRole("searchbox").fill("Москва");
  await page.getByRole("button", { name: "Москва Москва" }).click();
  await page.getByRole("button", { name: "Предыдущий шаг" }).click();
  await expect(page.getByRole("button", { name: "9 класс" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", { name: "Далее", exact: true }).click();
  await page.getByRole("button", { name: "Далее", exact: true }).click();
  await page.getByRole("button", { name: "Олимпиады", exact: true }).click();
  await page.getByRole("button", { name: "Далее", exact: true }).click();
  await page.getByRole("textbox").fill("Хочу изучать физику");
  await overflow();
  await page.getByRole("button", { name: "Открыть возможности" }).click();
  await expect(page.getByText("2 возможностей", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Что для тебя важно?" }),
  ).toBeVisible();
  await overflow();
  await page.getByRole("button", { name: "☷ Все фильтры" }).click();
  await page.getByRole("button", { name: "Сбросить", exact: true }).click();
  await page.getByRole("button", { name: "Закрыть фильтры" }).click();
  await expect(page.getByText("2 возможностей", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "☷ Все фильтры" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "☷ Все фильтры" }).click();
  await page.getByRole("button", { name: "Сбросить", exact: true }).click();
  await page.getByRole("button", { name: "Применить", exact: true }).click();
  await expect(
    page.getByText("16 возможностей", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Бесплатно", exact: true }).click();
  await expect(page.getByText("8 возможностей", { exact: true })).toBeVisible();
  await page.getByRole("button").filter({ hasText: "Вектор знаний" }).click();
  await expect(
    page.getByRole("heading", { name: "Вектор знаний" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Настоящей ссылки и приёма заявок нет/),
  ).toBeVisible();
  await overflow();
  await page.getByRole("button", { name: "← К подборке" }).click();
  await page.getByRole("button", { name: "◎ Профиль" }).click();
  await page.getByRole("button", { name: "Редактировать профиль" }).click();
  await page.getByRole("button", { name: "10 класс" }).click();
  for (let i = 0; i < 3; i++)
    await page.getByRole("button", { name: "Далее", exact: true }).click();
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  await page.getByRole("button", { name: "◎ Профиль" }).click();
  await expect(
    page.getByRole("heading", { name: "10 класс · Москва" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
