(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x78 (bvshl independent_opaque_0 (bvand (_ bv19 32) (_ bv31 32)))))
(let ((?x47 (bvadd ?x78 independent_opaque_1)))
(let ((?x10 (bvadd independent_opaque_1 ?x78)))
(and (distinct ?x10 ?x47) true)))))
(check-sat)
