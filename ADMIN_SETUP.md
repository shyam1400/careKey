# CareKey admin setup

CareKey never lets a browser choose its own role. New Firebase accounts start as patients. An administrator must provision doctor access from the protected Admin page.

## Bootstrap the first administrator

Because this installation has no administrator yet, bootstrap the first one directly in the Supabase SQL Editor. Use the account you control and have already signed into CareKey at least once so it exists in the backend database. Keep the SQL Editor restricted to trusted project owners.

1. In Supabase, open **SQL Editor** and find the account:

   ```sql
   select id, email, role
   from public.users
   where lower(email) = lower('YOUR_ADMIN_EMAIL');
   ```

2. Confirm the result is exactly your account. Copy its `id`, then run:

   ```sql
   update public.users
   set role = 'admin'
   where id = 'PASTE_YOUR_ACCOUNT_ID'::uuid
     and lower(email) = lower('YOUR_ADMIN_EMAIL');
   ```

3. Verify that one row now has the `admin` role:

   ```sql
   select id, email, role
   from public.users
   where id = 'PASTE_YOUR_ACCOUNT_ID'::uuid;
   ```

4. Sign out of CareKey and sign in again. The API checks roles in the database, and a new session reloads the Admin navigation.

Only bootstrap an account you control. The app intentionally does not expose a public first-admin endpoint. Admin roles cannot be assigned or changed from the browser UI.

## Provision doctors

1. Have the demo doctor create an account through the normal CareKey sign-up page and sign in once. That creates the backend user record as a patient.
2. As the administrator, open **Admin → Users**, set that account's role to **Doctor**, enter a synthetic name, organization, and specialty, then save.
3. The doctor signs out and back in. Patients can then select the doctor in **Sharing**. Use synthetic accounts and data only.

The Admin page can also add fictional hospitals to the directory. A hospital is a directory record, not a user account. Do not enter real patient information or rely on demo hospital listings for care decisions.
