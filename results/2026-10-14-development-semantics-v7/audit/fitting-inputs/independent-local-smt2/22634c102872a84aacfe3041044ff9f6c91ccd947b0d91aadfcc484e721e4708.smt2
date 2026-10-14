(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x25 (bvadd independent_opaque_1 (_ bv4294966072 32))))
(let ((?x23 (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32)))))
(let ((?x51 (bvadd ?x23 ?x25)))
(let ((?x42 (bvadd ?x25 ?x23)))
(and (distinct ?x42 ?x51) true))))))
(check-sat)
