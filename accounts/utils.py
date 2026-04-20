"""
apps/accounts/utils.py

Credential generation and user creation utilities.

Design decisions:
- Usernames are deterministic and human-readable (not random UUIDs)
  so admins can recognize them: john.mwangi.gfa or student.GFA001
- Passwords are random 10-char alphanumeric — strong enough, copyable
- Credentials are returned ONCE at creation time for display/printing
- After first login, user is forced to change password
- We NEVER store plaintext passwords — only show at creation moment
"""
import secrets
import string
import random
from django.utils.text import slugify


# Characters for auto-generated passwords
# Avoiding ambiguous chars: 0/O, 1/l/I
_PASSWORD_CHARS = (
    string.ascii_uppercase.replace('O', '').replace('I', '') +
    string.ascii_lowercase.replace('o', '').replace('l', '') +
    string.digits.replace('0', '').replace('1', '')
)


def generate_password(length=10):
    """
    Generate a random secure password.
    Always includes at least: 1 uppercase, 1 lowercase, 1 digit.
    """
    while True:
        pwd = ''.join(secrets.choice(_PASSWORD_CHARS) for _ in range(length))
        # Ensure complexity
        has_upper = any(c.isupper() for c in pwd)
        has_lower = any(c.islower() for c in pwd)
        has_digit = any(c.isdigit() for c in pwd)
        if has_upper and has_lower and has_digit:
            return pwd


def generate_username(first_name, last_name, org_slug, role_prefix='', existing_check_qs=None):
    """
    Generate a readable, unique username.

    Format:
        Admin:   admin.greenfield       (org-based)
        Teacher: john.mwangi.gfa        (name + org abbrev)
        Student: alice.njeri.gfa        (name + org abbrev)
        Parent:  parent.njeri.gfa       (role + name + org abbrev)

    If collision, appends a number: john.mwangi.gfa2
    """
    # Org abbreviation: first 3 chars of slug
    org_abbr = org_slug.replace('-', '')[:3].lower()

    first = slugify(first_name or 'user').replace('-', '')
    last = slugify(last_name or 'user').replace('-', '')

    if role_prefix:
        base = f"{role_prefix}.{last}.{org_abbr}"
    else:
        base = f"{first}.{last}.{org_abbr}"

    username = base
    counter = 2

    if existing_check_qs is not None:
        while existing_check_qs.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1

    return username


def generate_org_admin_username(org_slug):
    """
    Org admin username: admin.<orgslug-abbrev>
    e.g. admin.gfa for Greenfield Academy
    """
    abbr = org_slug.replace('-', '')[:6].lower()
    return f"admin.{abbr}"


def create_user_with_credentials(
    first_name, last_name, email='',
    organization=None, role=None,
    username=None, phone=''
):
    """
    Creates a user and returns (user, plaintext_password).

    The plaintext_password is the ONLY time it is available.
    Store it nowhere — display it once to the admin.

    Returns:
        tuple: (User instance, plaintext_password_string)
    """
    from accounts.models import User

    password = generate_password()

    if username is None:
        from accounts.models import User as U
        username = generate_username(
            first_name, last_name,
            org_slug=organization.slug if organization else 'sys',
            role_prefix='parent' if role == User.Role.PARENT else '',
            existing_check_qs=U.objects,
        )

    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        email=email,
        organization=organization,
        role=role,
        phone=phone,
        must_change_password=True,  # Force password change on first login
    )

    return user, password
