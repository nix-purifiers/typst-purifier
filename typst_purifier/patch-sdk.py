from pathlib import Path

p = Path("crates/typst-kit/src/downloader.rs")
s = p.read_text()
a = "        let mut builder = ureq::AgentBuilder::new();"
b = '        if std::env::var("TYPST_PURIFIER_FROZEN").as_deref() == Ok("1") {\n            return Err(std::io::Error::other("typst-purifier: dependency is absent from the locked Nix environment"));\n        }\n        let mut builder = ureq::AgentBuilder::new();'
assert s.count(a) == 1
p.write_text(s.replace(a, b))
p = Path("crates/typst-kit/src/packages.rs")
s = p.read_text()
a = "            Ok(data) => {\n                let decompressed = flate2::read::GzDecoder::new(Cursor::new(data));"
b = '            Ok(data) => {\n                if let Some(directory) = std::env::var_os("TYPST_PURIFIER_CAPTURE") {\n                    let directory = std::path::PathBuf::from(directory);\n                    std::fs::create_dir_all(&directory).map_err(|err| PackageError::NetworkFailed(Some(eco_format!("{err}"))))?;\n                    let filename = directory.join(format!("{}-{}.tar.gz", spec.name, spec.version));\n                    std::fs::write(&filename, &data).map_err(|err| PackageError::NetworkFailed(Some(eco_format!("{err}"))))?;\n                    std::fs::write(filename.with_extension("json"), serde_json::to_vec(&serde_json::json!({"url":url,"namespace":spec.namespace,"name":spec.name,"version":spec.version.to_string()})).map_err(|err| PackageError::NetworkFailed(Some(eco_format!("{err}"))))?).map_err(|err| PackageError::NetworkFailed(Some(eco_format!("{err}"))))?;\n                }\n                let decompressed = flate2::read::GzDecoder::new(Cursor::new(data));'
assert s.count(a) == 1
p.write_text(s.replace(a, b))
