(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x76 (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x958 (bvadd ?x76 (bvadd independent_opaque_1 (_ bv81 32)))))
(let ((?x556 (bvadd (bvadd ?x76 independent_opaque_1) (_ bv81 32))))
(and (distinct ?x556 ?x958) true)))))
(check-sat)
