(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x64 (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32)))))
(let ((?x983 (bvadd ?x64 independent_opaque_1)))
(let ((?x625 (bvadd independent_opaque_1 ?x64)))
(and (distinct ?x625 ?x983) true)))))
(check-sat)
