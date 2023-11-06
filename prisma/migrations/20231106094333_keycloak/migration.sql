/*
  Warnings:

  - A unique constraint covering the columns `[keycloakUserId]` on the table `ApiUser` will be added. If there are existing duplicate values, this will fail.

*/
-- AlterTable
ALTER TABLE "ApiUser" ADD COLUMN     "keycloakUserId" TEXT;

-- CreateIndex
CREATE UNIQUE INDEX "ApiUser_keycloakUserId_key" ON "ApiUser"("keycloakUserId");
