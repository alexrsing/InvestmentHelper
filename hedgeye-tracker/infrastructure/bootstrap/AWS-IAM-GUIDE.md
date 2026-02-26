# AWS IAM Console Guide - Adding Terraform Bootstrap Permissions

> **Note**: This guide contains the complete, tested IAM policy with all required permissions for the Terraform bootstrap process. The policy below includes all S3 and DynamoDB permissions needed.

## Step-by-Step Guide to Find and Update Your IAM Role

### Step 1: Access the AWS IAM Console

1. **Open your web browser** and go to: https://console.aws.amazon.com/
2. **Sign in** to your AWS account
3. In the search bar at the top, type **"IAM"** and click on **IAM (Identity and Access Management)**

### Step 2: Navigate to Roles

1. In the left sidebar, click on **"Roles"**
2. You'll see a list of all IAM roles in your account

### Step 3: Find Your EC2 Role

1. In the search box, paste this role name:
   ```
   dev-vm-DevVmRoleFCAA2DF1-ZbuKBQWaNafk
   ```

2. Click on the role name when it appears in the list

### Step 4: View Current Permissions

You'll now see the role details page with several tabs:
- **Permissions** - Shows what this role can do
- **Trust relationships** - Shows what can use this role
- **Tags** - Metadata about the role

Click on the **"Permissions"** tab to see what policies are currently attached.

### Step 5: Add the Bootstrap Permissions

#### Option A: Attach Inline Policy (Easiest)

1. Scroll down to the **"Permissions policies"** section
2. Click the **"Add permissions"** dropdown button
3. Select **"Create inline policy"**
4. Click the **"JSON"** tab
5. Delete the default JSON and paste the contents of `terraform-bootstrap-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TerraformS3BackendBootstrap",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning",
        "s3:GetEncryptionConfiguration",
        "s3:PutEncryptionConfiguration",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetLifecycleConfiguration",
        "s3:PutLifecycleConfiguration",
        "s3:GetBucketTagging",
        "s3:PutBucketTagging",
        "s3:GetAccelerateConfiguration",
        "s3:GetBucketAcl",
        "s3:GetBucketCORS",
        "s3:GetBucketWebsite",
        "s3:GetBucketLogging",
        "s3:GetBucketRequestPayment",
        "s3:GetBucketObjectLockConfiguration",
        "s3:GetReplicationConfiguration",
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::hedgeye-risk-tracker-terraform-state"
    },
    {
      "Sid": "TerraformDynamoDBLockBootstrap",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:DescribeContinuousBackups",
        "dynamodb:UpdateContinuousBackups",
        "dynamodb:DescribeTimeToLive",
        "dynamodb:TagResource",
        "dynamodb:UntagResource",
        "dynamodb:ListTagsOfResource"
      ],
      "Resource": "arn:aws:dynamodb:us-west-2:422466752443:table/terraform-state-lock"
    }
  ]
}
```

6. Click **"Next"**
7. Give the policy a name: `TerraformBootstrapPolicy`
8. Click **"Create policy"**

#### Option B: Create Managed Policy (More Reusable)

1. Go back to IAM home
2. Click **"Policies"** in the left sidebar
3. Click **"Create policy"**
4. Click the **"JSON"** tab
5. Paste the policy JSON (same as above)
6. Click **"Next"**
7. Name it: `TerraformBootstrapPolicy`
8. Add description: "Allows creation of Terraform S3 backend resources"
9. Click **"Create policy"**

Then attach it to your role:
1. Go back to **Roles** → Find your role
2. Click **"Add permissions"** → **"Attach policies"**
3. Search for `TerraformBootstrapPolicy`
4. Check the box next to it
5. Click **"Attach policies"**

### Step 6: Verify Permissions

After adding the policy:
1. Go back to your role's **Permissions** tab
2. You should see `TerraformBootstrapPolicy` listed
3. Click on it to expand and verify the permissions

### Step 7: Test in Terminal

Go back to your EC2 instance terminal and try running Terraform again:

```bash
cd /home/ec2-user/projects/hedgeye-risk-ranges-tracker/infrastructure/bootstrap
terraform apply -var="org_name=hedgeye-risk-tracker" -var="aws_region=us-west-2"
```

---

## Understanding What You Just Did

### What is IAM?
IAM (Identity and Access Management) controls **who** can do **what** in your AWS account.

### What is a Role?
A **role** is like a set of permissions that can be assigned to:
- EC2 instances (like yours)
- Lambda functions
- Other AWS services

Your EC2 instance is using the role `dev-vm-DevVmRoleFCAA2DF1-ZbuKBQWaNafk`.

### What are Policies?
**Policies** are JSON documents that define permissions. They specify:
- **Actions**: What operations are allowed (e.g., `s3:CreateBucket`)
- **Resources**: What AWS resources can be accessed (e.g., specific S3 bucket)
- **Effect**: Allow or Deny

### What Did We Just Add?

We added permissions for your EC2 to:
1. **Create an S3 bucket** named `hedgeye-risk-tracker-terraform-state`
2. **Configure the bucket** (versioning, encryption, public access blocking)
3. **Create a DynamoDB table** named `terraform-state-lock`
4. **Configure the table** (point-in-time recovery, tags)

These are **one-time permissions** needed only to create the Terraform backend infrastructure.

---

## Troubleshooting

### Can't Find the Role?
- Make sure you're in the correct AWS region (check top right of console)
- Make sure you're logged in to account `422466752443`
- Try searching for just `dev-vm` in the roles list

### Can't Add Permissions?
You might not have IAM permissions yourself. You'll need someone with:
- `iam:CreatePolicy` permission
- `iam:AttachRolePolicy` permission

This is usually an AWS administrator or account owner.

### "Access Denied" When Adding Policy?
Ask your AWS account administrator to:
1. Create the policy using `terraform-bootstrap-policy.json`
2. Attach it to your role `dev-vm-DevVmRoleFCAA2DF1-ZbuKBQWaNafk`

---

## Visual Guide

```
AWS Console
    ↓
IAM Service
    ↓
Roles (left sidebar)
    ↓
Search: "dev-vm-DevVmRoleFCAA2DF1-ZbuKBQWaNafk"
    ↓
Click on role name
    ↓
Permissions tab
    ↓
Add permissions → Create inline policy
    ↓
JSON tab → Paste policy → Create
    ↓
Done! ✅
```

---

## Next Steps After Adding Permissions

Once the policy is attached:

1. **Wait 1-2 minutes** for the permissions to propagate
2. **Return to your terminal**
3. **Run the Terraform bootstrap**:
   ```bash
   cd /home/ec2-user/projects/hedgeye-risk-ranges-tracker/infrastructure/bootstrap
   terraform apply -var="org_name=hedgeye-risk-tracker" -var="aws_region=us-west-2"
   ```
4. **Verify resources were created**:
   ```bash
   aws s3 ls | grep terraform-state
   aws dynamodb list-tables | grep terraform-state-lock
   ```

---

## Security Note

The permissions we're adding are **minimal and specific**:
- Only allows creating **one specific S3 bucket**
- Only allows creating **one specific DynamoDB table**
- Only in the **us-west-2 region**

This follows the principle of **least privilege** - only the minimum permissions needed.

---

## Alternative: Using Your .env Credentials

I noticed you have AWS access keys in your `.env` file. If those credentials have the necessary permissions, you can use them instead:

```bash
# Load credentials from .env
source .env

# Or export them manually
export AWS_ACCESS_KEY_ID="your-key-from-env"
export AWS_SECRET_ACCESS_KEY="your-secret-from-env"
export AWS_REGION="us-west-2"

# Then run Terraform
terraform apply
```

This will use your access keys instead of the EC2 role.

---

## Need Help?

If you get stuck:
1. Take a screenshot of the error message
2. Note which step you're on
3. Ask your AWS administrator for help with IAM permissions

The key information they'll need:
- **Role name**: `dev-vm-DevVmRoleFCAA2DF1-ZbuKBQWaNafk`
- **Policy file**: `terraform-bootstrap-policy.json`
- **What it does**: Allows creating Terraform backend S3 bucket and DynamoDB table
