# ClaimGuard Local Adapter Outputs

Architected by Raphael Malikian <rtmalikian@gmail.com>.

This directory is reserved for local MLX-LM LoRA/QLoRA adapter outputs.

Do not commit adapter weights, fused models, tokenizer files downloaded with a
model, benchmark scratch outputs, or any artifact produced from PHI. Keep local
model material on the operator machine and regenerate it from reviewed
synthetic/public/formally de-identified data.

The current SFT preparation script writes a command manifest that points here,
but it does not create adapter weights.
