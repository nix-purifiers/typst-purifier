from pathlib import Path

p = Path("crates/tinymist-package/src/registry/http.rs")
s = p.read_text()
a = "    pub fn download_index(&self) -> &[PackageIndexEntry] {\n        self.index.get_or_init(|| {"
b = '    pub fn download_index(&self) -> &[PackageIndexEntry] {\n        if std::env::var("TYPST_PURIFIER_FROZEN").as_deref() == Ok("1") {\n            return &[];\n        }\n        self.index.get_or_init(|| {'
assert s.count(a) == 1
s = s.replace(a, b)
a = '        assert!(spec.is_preview(), "only preview packages can be downloaded");'
b = '        if std::env::var("TYPST_PURIFIER_FROZEN").as_deref() == Ok("1") {\n            return Err(PackageError::Other(Some(eco_format!("typst-purifier: dependency is absent from the locked Nix environment"))));\n        }\n        assert!(spec.is_preview(), "only preview packages can be downloaded");'
assert s.count(a) == 1
s = s.replace(a, b)
p.write_text(s)

s = p.read_text()
a = """        Self {
            cert_path,
            package_path,
            package_cache_path,
            ..Default::default()
        }"""
b = """        let frozen = std::env::var("TYPST_PURIFIER_FROZEN").as_deref() == Ok("1");
        let package_path = if frozen {
            Some(std::path::PathBuf::from(std::env::var_os("TYPST_PACKAGE_PATH").expect("typst-purifier: missing locked package path")).into())
        } else { package_path };
        let package_cache_path = if frozen {
            Some(std::path::PathBuf::from(std::env::var_os("TYPST_PACKAGE_CACHE_PATH").expect("typst-purifier: missing locked cache path")).into())
        } else { package_cache_path };
        Self {
            cert_path,
            package_path,
            package_cache_path,
            ..Default::default()
        }"""
assert s.count(a) == 1
s = s.replace(a, b)
p.write_text(s)
