import { expect, test } from "@playwright/test";

test.describe("/ipam/addresses - IP Address list", () => {
  test("view the ip address list, use the pagination and view ip address summary", async ({
    page,
  }) => {
    await page.goto("/ipam/addresses?ipam-tab=ip-details");
    await expect(page.getByText("Showing 1 to ")).toBeVisible();
    await page.getByTestId("ipam-main-content").getByTestId("select-open-option-button").click();
    await page.getByRole("option", { name: "20" }).click();
    await expect(page.getByText("Showing 1 to 20 of ")).toBeVisible();

    await page
      .getByTestId("ipam-main-content")
      .getByRole("link", { name: "10.0.0.16/32" }) // prefix need pagination to be visible
      .click();
    expect(page.url()).toContain("/ipam/addresses/");
    expect(page.url()).toContain("ipam-tab=ip-details");

    await expect(page.getByText("Ipam IP Address summary")).toBeVisible();
    await expect(page.getByText("Address10.0.0.16/32")).toBeVisible();
    await expect(page.getByText("InterfaceLoopback0")).toBeVisible();
    await expect(page.getByText("Ip Prefix10.0.0.0/16")).toBeVisible();

    await page.getByRole("link", { name: "All IP Addresses" }).click();
    await expect(page.getByText("Showing 1 to ")).toBeVisible();
  });

  test("view all ip addresses under a given prefix", async ({ page }) => {
    await page.goto("/ipam/addresses?ipam-tab=ip-details");

    await test.step("select a prefix to view all ip addresses", async () => {
      await page.getByRole("treeitem", { name: "172.20.20.0/27" }).click();
      await expect(page.getByText("172.20.20.0/27IP Addresses")).toBeVisible();
      await expect(page.getByText("Showing 1 to ")).toBeVisible();
    });

    await test.step("click on any ip address row to view summary", async () => {
      await page.getByRole("link", { name: "172.20.20.1/28" }).click();
      await expect(page.getByText("Ipam IP Address summary")).toBeVisible();
      await expect(page.url()).toContain("ipam-tab=ip-details");
    });

    await test.step("use breadcrumb to go back to parent prefix", async () => {
      await page.getByRole("link", { name: "All IP Addresses" }).click();
      await expect(page.getByText("Showing 1 to ")).toBeVisible();
      await expect(page.locator("[aria-selected=true]")).toContainText("172.20.20.0/27");
      await expect(page.url()).toContain("/prefixes/");
    });
  });
});
