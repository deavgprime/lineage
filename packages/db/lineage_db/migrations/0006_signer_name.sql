-- Keep the signer's username with each sign-off, so the file shows who signed without a lookup.
ALTER TABLE sign_offs ADD COLUMN signer_name text;
