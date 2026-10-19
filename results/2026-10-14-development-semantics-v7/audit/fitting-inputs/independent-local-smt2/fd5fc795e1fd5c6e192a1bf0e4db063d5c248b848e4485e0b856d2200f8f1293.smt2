(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1000 (bvadd independent_opaque_0 (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv30 32) (_ bv31 32)))))))
(let ((?x126 (bvshl independent_opaque_1 (bvand (_ bv30 32) (_ bv31 32)))))
(let ((?x682 (bvsub independent_opaque_0 ?x126)))
(and (distinct ?x682 ?x1000) true)))))
(check-sat)
