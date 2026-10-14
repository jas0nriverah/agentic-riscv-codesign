(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x222 (bvadd independent_opaque_1 (_ bv4294967039 32))))
(let ((?x402 (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32)))))
(let ((?x85 (bvadd ?x402 ?x222)))
(let ((?x33 (bvadd ?x222 ?x402)))
(and (distinct ?x33 ?x85) true))))))
(check-sat)
