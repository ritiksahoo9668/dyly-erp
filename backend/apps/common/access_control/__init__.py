"""ERP access control: Module -> Submodule -> Action permissions layered under global roles.

Global roles (SUPERADMIN / ADMIN / USER) decide the account level; this package decides which
parts of the ERP an account may use. Document-level workflow authority (assignment, approval
level, financial limits) is never granted here and must be checked separately.
"""
